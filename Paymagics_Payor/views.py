from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .serializers import *
from .models import *
from Paymagics_Admin.models import UserProfile, UserRole
import random, string
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
import openpyxl
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
from datetime import datetime
from io import BytesIO
from django.core.mail import send_mail
import uuid
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from Paymagics_PayorStaff.models import PaymentTemplate
from django.utils import timezone
from django.db.models import Count, Q
from openpyxl import Workbook
from openpyxl.styles import Font


#create (input:category,payee-optional) or edit (input:category-id, payee-optional) list
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_or_update_category(request):
    category_input = request.data.get("category")         
    new_category_name = request.data.get("new_name")      
    payee_id = request.data.get("payee")             

    if not category_input and not payee_id:
        return Response(
            {"error": "Provide at least a category (name or ID) or a payee ID."},
            status=status.HTTP_400_BAD_REQUEST
        )

    category = None
    message = ""

    # Try interpreting category as ID
    try:
        category_id = int(category_input)
        category = Category.objects.filter(id=category_id).first()
        if not category:
            return Response({"error": "Category with this ID not found."}, status=status.HTTP_404_NOT_FOUND)
        message = "Category found by ID."
    except (TypeError, ValueError):
        # Not an integer, treat as category name (create or fetch)
        category_name = category_input
        category = Category.objects.filter(category__iexact=category_name).first()
        if not category:
            # Create new category with count 0
            category = Category.objects.create(category=category_name, count=0)
            message = "New category created."
        else:
            message = "Category exists."

    # Rename if new_name provided
    if new_category_name:
        if Category.objects.filter(category__iexact=new_category_name).exclude(id=category.id).exists():
            return Response({"error": "A category with the new name already exists."}, status=status.HTTP_400_BAD_REQUEST)

        old_name = category.category
        category.category = new_category_name
        category.save()
        message += f" Renamed from '{old_name}' to '{new_category_name}'."

    # Handle payee-category linking
    if payee_id:
        try:
            payee = Payee.objects.get(id=payee_id, is_active=True)
        except Payee.DoesNotExist:
            return Response({"error": "Payee not found."}, status=status.HTTP_404_NOT_FOUND)

        if not payee.categories.filter(id=category.id).exists():
            payee.categories.add(category)
            category.count += 1
            category.save()
            message += " Category assigned to payee and count incremented."
        else:
            message += " Category already assigned to this payee."

    return Response({
        "id": category.id,
        "category": category.category,
        "count": category.count,
        "message": message
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated]) 
def create_payee(request):
    serializer = CreatePayeeSerializer(data=request.data)
    
    if serializer.is_valid():
        data = serializer.validated_data
        payee_type = data["payee_type"]

        # Generate referral code
        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # Get UserProfile of the logged-in user
        try:
            payor = UserProfile.objects.get(user=request.user)
        except UserProfile.DoesNotExist:
            return Response({'error': 'Associated payor profile not found.'}, status=400)

        # Get category
        category_id = data.get("category")
        try:
            category = Category.objects.get(id=category_id)
        except Category.DoesNotExist:
            return Response({'error': 'Invalid category ID.'}, status=400)

        # Create Payee
        payee = Payee.objects.create(
            ben_code=data["ben_code"],
            ben_name=data["ben_name"],
            add1=data["add1"],
            add2=data["add2"],
            city=data["city"],
            state=data["state"],
            zipcode=data["zipcode"],
            contact=data["contact"],
            email=data["email"],
            acc_no=data.get("acc_no"),
            ifsc=data.get("ifsc"),
            iban=data.get("iban"),
            swift_code=data.get("swift_code"),
            sort_code=data.get("sort_code"),
            bank_name=data.get("bank_name"),
            branch=data.get("branch"),
            bank_account_type=data.get("bank_account_type"),
            referralcode=referral_code,
            payee_type=payee_type,
            payor=payor
        )
        payee.categories.add(category)
        category.count += 1
        category.save()

        return Response(PayeeSerializer(payee).data, status=201)
    
    return Response(serializer.errors, status=400)


#edit payee
@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def edit_payee(request, pk):
    if not pk:
        return Response(
            {'error': 'Missing payee ID (pk) in query params.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        payee = Payee.objects.get(pk=pk)
    except Payee.DoesNotExist:
        return Response({'error': 'Payee not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        UserProfile.objects.get(user=request.user)  # just to confirm payor exists
    except UserProfile.DoesNotExist:
        return Response({'error': 'Payor profile not found.'}, status=status.HTTP_400_BAD_REQUEST)

    serializer = UpdatePayeeSerializer(instance=payee, data=request.data, partial=True)

    if serializer.is_valid():
        for attr, value in serializer.validated_data.items():
            if attr != 'categories':  
                setattr(payee, attr, value)

        payee.save()
        return Response(PayeeSerializer(payee).data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


#delete payee
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_payee(request, pk):
    if not pk:
        return Response({'error': 'Missing payee ID (pk).'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        payee = Payee.objects.get(pk=pk)
    except Payee.DoesNotExist:
        return Response({'error': 'Payee not found.'}, status=status.HTTP_404_NOT_FOUND)

    try:
        payor = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return Response({'error': 'Payor profile not found.'}, status=status.HTTP_400_BAD_REQUEST)

    if payee.payor != payor:
        return Response({'error': 'You are not authorized to delete this payee.'}, status=status.HTTP_403_FORBIDDEN)

    #  Soft delete
    payee.is_active = False
    payee.save()

    return Response({'message': 'Payee marked as deleted.'}, status=status.HTTP_200_OK)


#view all payee - paginated
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payee_list(request):
    queryset = Payee.objects.filter(is_active=True)

    paginator = PageNumberPagination()
    paginator.page_size = 5

    result_page = paginator.paginate_queryset(queryset, request)
    serializer = PayeeSerializer(result_page, many=True)

    return paginator.get_paginated_response(serializer.data)


#single payee view
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payee_detail(request, pk):
    try:
        payee = Payee.objects.get(pk=pk, is_active=True)
    except Payee.DoesNotExist:
        return Response({'error': 'Payee not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    serializer = PayeeSerializer(payee)
    return Response(serializer.data, status=status.HTTP_200_OK)


#view all lists - paginated
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def view_list(request):
    queryset = Category.objects.all()

    paginator = PageNumberPagination()
    paginator.page_size = 5 

    result_page = paginator.paginate_queryset(queryset, request)
    serializer = CategorySerializer(result_page, many=True)

    return paginator.get_paginated_response(serializer.data)


#delete category
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_categ(request, pk):
    if not pk:
        return Response({'error': 'Missing category ID (pk).'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        category = Category.objects.get(pk=pk)
    except Category.DoesNotExist:
        return Response({'error': 'Category not found.'}, status=status.HTTP_404_NOT_FOUND)

    category.delete()

    return Response({'message': 'Category deleted successfully.'}, status=status.HTTP_200_OK)


#payee list export to excel based on template
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def export_payees_excel(request, template_id):
    # Handle GET vs POST inputs
    if request.method == "GET":
        query = request.GET.get("q", "")
        download = request.GET.get("download", "false").lower() == "true"
    else:  # POST
        query = request.data.get("q", "")
        download = str(request.data.get("download", "false")).lower() == "true"

    # Get template (needed only for Excel)
    try:
        template = PaymentTemplate.objects.get(id=template_id)
    except PaymentTemplate.DoesNotExist:
        return HttpResponse("Template not found.", status=404)

    # Base queryset
    payees = Payee.objects.filter(is_active=True)

    # Filtering
    if query:
        matching_categories = Category.objects.filter(category__icontains=query)
        payees = payees.filter(
            Q(ben_code__icontains=query) |
            Q(ben_name__icontains=query) |
            Q(contact__icontains=query) |
            Q(email__icontains=query) |
            Q(categories__in=matching_categories)
        ).distinct()

    if not payees.exists():
        return HttpResponse("No payees found.", status=404)

    # 👉 If not downloading, return paginated JSON (view mode)
    if not download:
        paginator = PageNumberPagination()
        paginator.page_size = 5
        result_page = paginator.paginate_queryset(payees, request)
        serializer = PayeeSerializer(result_page, many=True)
        return paginator.get_paginated_response(serializer.data)

    # 👉 Otherwise, export as Excel
    dynamic_fields = template.dynamic_fields or {}
    static_fields = template.static_fields or {}

    dynamic_headers = list(dynamic_fields.keys())
    static_headers = list(static_fields.keys())
    headers = dynamic_headers + static_headers

    wb = Workbook()
    ws = wb.active
    ws.title = template.name or "Payee Export"

    # Add template name
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(headers))
    title_cell = ws.cell(row=1, column=1, value=f"Template: {template.name}")
    title_cell.font = Font(bold=True, size=14)

    # Headers
    for col_num, header in enumerate(headers, start=1):
        cell = ws.cell(row=2, column=col_num, value=header)
        cell.font = Font(bold=True)

    # Data
    for row_num, payee in enumerate(payees, start=3):
        for col_num, header in enumerate(headers, start=1):
            if header in dynamic_fields:
                model_field = dynamic_fields[header]
                value = getattr(payee, model_field, "")
            else:
                value = static_fields.get(header, "")
            ws.cell(row=row_num, column=col_num, value=value)

    # Auto column width
    for col_num, _ in enumerate(headers, start=1):
        col_letter = get_column_letter(col_num)
        max_length = max(
            len(str(ws.cell(row=row, column=col_num).value or "")) 
            for row in range(1, ws.max_row + 1)
        )
        ws.column_dimensions[col_letter].width = max_length + 5

    file_stream = BytesIO()
    wb.save(file_stream)
    file_stream.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{template.name}_payees_export_{timestamp}.xlsx"

    response = HttpResponse(
        file_stream.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response



#referrel
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def send_invitation(request):
    try:
        payor_profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return Response({"error": "Payor profile not found."}, status=400)

    email = request.data.get("email")
    if not email:
        return Response({"error": "Payee email is required."}, status=400)
    email = email.strip().lower()

    if email == payor_profile.user.email.lower():
        return Response({"error": "You cannot invite yourself."}, status=400)

    try:
        payee = Payee.objects.get(email=email, is_active=True)
    except Payee.DoesNotExist:
        return Response({"error": "Payee not found."}, status=400)

    invite, created = ReferralInvite.objects.get_or_create(
        payor=payor_profile,
        payee_email=email,
        defaults={
            "status": "pending",
            "referral_code": str(uuid.uuid4())
        }
    )

    if created:
        invite_link = request.build_absolute_uri(f"{invite.referral_code}/complete/")


        send_mail(
            subject="You've been invited!",
            message=f"Complete your profile here: {invite_link}",
            from_email=payor_profile.user.email,
            recipient_list=[email],
            fail_silently=False
        )

        return Response({"message": f"Invitation sent to {email}",
                         "referral_code":f"{invite.referral_code}"}, status=200)
    else:
        return Response({"message": f"Invitation already exists for {email}."}, status=200)

#referrel clicked status conversion
@api_view(["GET"])
@permission_classes([AllowAny])
def referral_details(request, referral_code):
    invite = get_object_or_404(ReferralInvite, referral_code=referral_code)
    if invite.status == "pending":
        invite.status = "clicked"
        invite.save()

    return Response({
        "payee_email": invite.payee_email,
        "status": invite.status
    })

#referral - update payee profile
@api_view(["POST"])
@permission_classes([AllowAny])
def complete_payee_profile(request, referral_code):
    invite = get_object_or_404(ReferralInvite, referral_code=referral_code)

    try:
        payee = Payee.objects.get(email=invite.payee_email)
    except Payee.DoesNotExist:
        return Response({"error": "Payee profile not found."}, status=404)

    serializer = UpdatePayeeSerializer(payee, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        invite.status = "completed"
        invite.save()
        return Response({"message": "Profile updated successfully."})

    return Response(serializer.errors, status=400)



#view payees corresponding to list
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payees_in_list(request, category):
    payees = Payee.objects.filter(categories__id=category, is_active=True)

    if not payees.exists():
        return Response({'error': 'No payees found for this category.'}, status=status.HTTP_404_NOT_FOUND)

    paginator = PageNumberPagination()
    paginator.page_size = 5

    result_page = paginator.paginate_queryset(payees, request)
    serializer = PayeeSerializer(result_page, many=True)

    return paginator.get_paginated_response(serializer.data)



#dashboard -payee
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_counts(request):
    # Total categories
    total_categories = Category.objects.count()

    # Active categories: categories with at least one active payee
    active_categories = Category.objects.annotate(
        active_payees_count=Count('payees', filter=Q(payees__is_active=True))
    ).filter(active_payees_count__gt=0).count()

    # Total payees
    total_payees = Payee.objects.count()

    data = {
        "total_lists": total_categories,
        "active_lists": active_categories,
        "total_payees": total_payees
    }

    return Response(data, status=200)


#------------------------delete file
@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_files(request, batch_name):
    if not batch_name:
        return Response({"error": "Batch name is required."}, status=400)

    deleted_count, _ = TemplatePayee.objects.filter(batch_name=batch_name).delete()

    if deleted_count == 0:
        return Response({"message": f"No TemplatePayees found for batch '{batch_name}'."}, status=404)

    return Response({"message": f" file '{batch_name}' deleted."})



# ----------------------------- fetch options of payment template
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def payment_template_options(request, template_id):
    try:
        template = PaymentTemplate.objects.get(id=template_id, template_type="payment")
    except PaymentTemplate.DoesNotExist:
        return Response({"error": "Payee template not found."}, status=404)

    return Response({
        "id": template.id,
        "template_name": template.name,
        "options": template.options or {},
    })
