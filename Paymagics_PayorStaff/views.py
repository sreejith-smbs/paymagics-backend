from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.http import HttpResponse
from openpyxl import Workbook
from .models import PaymentTemplate, TemplatePayee, PaymentTemp
from Paymagics_Payor.models import Payee
from .serializers import PaymentTemplateSerializer, TemplatePayeeSerializer, PaymentTempSerializer
from django.shortcuts import get_object_or_404
from django.forms.models import model_to_dict
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from django.http import HttpResponse
from django.utils import timezone
from django.urls import reverse
from rest_framework.pagination import PageNumberPagination



# -----------------------------PaymentTemplate Views

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def templates(request):
    template_type = request.query_params.get("type")

    if template_type not in ["payment", "payee"]:
        return Response({"error": "Invalid or missing template type"}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'GET':
        templates = PaymentTemplate.objects.filter(template_type=template_type)
        
        paginator = PageNumberPagination()
        paginator.page_size = 10  
        paginated_templates = paginator.paginate_queryset(templates, request)
        serializer = PaymentTemplateSerializer(paginated_templates, many=True)
        return paginator.get_paginated_response(serializer.data)

    elif request.method == 'POST':
        name = request.data.get("name")
        if PaymentTemplate.objects.filter(name=name).exists():
            return Response(
                {"error": f"Template with name '{name}' already exists"},
                status=status.HTTP_400_BAD_REQUEST
            )

        data = request.data.copy()
        data["template_type"] = template_type   

        serializer = PaymentTemplateSerializer(data=data)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def payment_template_detail(request, pk):
    template = get_object_or_404(PaymentTemplate, pk=pk)

    if request.method == 'GET':
        serializer = PaymentTemplateSerializer(template)
        return Response(serializer.data)

    elif request.method == 'PUT':
        serializer = PaymentTemplateSerializer(template, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save(created_by=request.user)
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        template.delete()
        return Response({"detail": "Template deleted successfully."}, status=status.HTTP_204_NO_CONTENT)


# ----------------------------- Add payee to template
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_payees_to_template(request, template_id):
    try:
        template = PaymentTemplate.objects.get(id=template_id)
    except PaymentTemplate.DoesNotExist:
        return Response({"error": "Template not found"}, status=status.HTTP_404_NOT_FOUND)

    if template.template_type != "payment":
        return Response(
            {"error": "Payees can only be added to 'payment' type templates"},
            status=status.HTTP_400_BAD_REQUEST
        )

    payees_data = request.data.get("payees", [])
    batch_name = request.data.get("batch_name")

    if not batch_name:
        batch_name = f"Batch_{timezone.now().strftime('%Y%m%d%H%M')}"

    if TemplatePayee.objects.filter(batch_name=batch_name).exists():
        return Response(
            {"error": f"Batch name '{batch_name}' already exists"},
            status=status.HTTP_400_BAD_REQUEST
        )

    created_payees = []

    for data in payees_data:
        payee_id = data.get("payee_id")

        try:
            payee = Payee.objects.get(id=payee_id)
        except Payee.DoesNotExist:
            continue

        payee_dict = model_to_dict(payee)

        dynamic_fields_map = template.dynamic_fields or {}
        dynamic_data = {
            header: payee_dict.get(model_field)
            for header, model_field in dynamic_fields_map.items()
            if model_field in payee_dict
        }

        static_data = template.static_fields or {}

        options_data = data.get("options_data", {})

        template_payee = TemplatePayee.objects.create(
            template=template,
            payee=payee,
            dynamic_data=dynamic_data,
            static_data=static_data,
            options_data=options_data,
            batch_name=batch_name
        )
        created_payees.append(template_payee)
    serializer = TemplatePayeeSerializer(created_payees, many=True)
    return Response({
        "template": PaymentTemplateSerializer(template).data,
        "batch_name": batch_name,
        "payees": serializer.data
    }, status=status.HTTP_201_CREATED)



# ----------------------------- download excel 
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_batch_excel(request, batch_name):
    payees = TemplatePayee.objects.filter(batch_name=batch_name)

    if not payees.exists():
        return Response({"error": "No payees found for this batch"}, status=404)

    template = payees.first().template

    wb = Workbook()
    ws = wb.active
    ws.title = batch_name

    dynamic_headers = list(template.dynamic_fields.keys()) if template.dynamic_fields else []
    static_headers = list(template.static_fields.keys()) if template.static_fields else []
    options_headers = list(template.options.keys()) if template.options else []

    headers = dynamic_headers + static_headers + options_headers

    for col_num, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.font = Font(bold=True)

    for row_num, tp in enumerate(payees, start=2):
        for col_num, h in enumerate(headers, start=1):
            value = ""
            if tp.dynamic_data and h in tp.dynamic_data:
                value = tp.dynamic_data[h]
            elif tp.static_data and h in tp.static_data:
                value = tp.static_data[h]
            elif tp.options_data and h in tp.options_data:
                value = tp.options_data[h]
            ws.cell(row=row_num, column=col_num, value=value)

    for col_num, header in enumerate(headers, start=1):
        col_letter = get_column_letter(col_num)
        max_length = max(
            len(str(ws.cell(row=row, column=col_num).value or "")) for row in range(1, ws.max_row + 1)
        )
        ws.column_dimensions[col_letter].width = max_length + 5

    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{batch_name}.xlsx"'
    wb.save(response)
    return response



# ----------------------------- excel files
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_batches(request):
    batches = (
        TemplatePayee.objects
        .values("batch_name", "template__id", "template__name")
        .distinct()
    )

    data = []
    for batch in batches:
        data.append({
            "batch_name": batch["batch_name"],
            "template_id": batch["template__id"],
            "template_name": batch["template__name"],
            "download_url": request.build_absolute_uri(
                reverse("download_batch_excel", args=[batch["batch_name"]])
            )
        })

    paginator = PageNumberPagination()
    paginator.page_size = 10
    paginated_data = paginator.paginate_queryset(data, request)

    return paginator.get_paginated_response(paginated_data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_batch_excel(request, batch_name):
    payees = TemplatePayee.objects.filter(batch_name=batch_name)
    if not payees.exists():
        return Response({"error": "Batch not found."}, status=status.HTTP_404_NOT_FOUND)

    # All payees in the same batch share one template
    template = payees.first().template  

    payees_data = TemplatePayeeSerializer(payees, many=True).data
    template_data = PaymentTemplateSerializer(template).data

    response_data = {
        "batch_name": batch_name,
        "template": template_data,
        "total_records": len(payees_data),
        "records": payees_data
    }

    return Response(response_data, status=status.HTTP_200_OK)


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_batch_excel(request, batch_name):
    data = request.data
    if not isinstance(data, list):
        return Response({"error": "Expected a list of payee objects."}, status=400)

    payees = TemplatePayee.objects.filter(batch_name=batch_name)
    if not payees.exists():
        return Response({"error": "Batch not found."}, status=404)

    template = payees.first().template
    updated_items = []
    created_items = []

    for item in data:
        payee_id = item.get("id")

        # Update existing record
        if payee_id:
            try:
                payee = TemplatePayee.objects.get(id=payee_id, batch_name=batch_name)
            except TemplatePayee.DoesNotExist:
                continue  # skip invalid IDs

            serializer = TemplatePayeeSerializer(payee, data=item, partial=True)
            if serializer.is_valid():
                serializer.save()
                updated_items.append(serializer.data)
            else:
                return Response(serializer.errors, status=400)

        # Create new record
        else:
            # Require payee field for new creation
            if not item.get("payee"):
                return Response({"error": "payee ID is required for new entries."}, status=400)

            serializer = TemplatePayeeSerializer(data={
                "template": template.id,
                "payee": item["payee"],
                "batch_name": batch_name,
                "dynamic_data": item.get("dynamic_data", {}),
                "static_data": item.get("static_data", {}),
                "options_data": item.get("options_data", {}),
            })
            if serializer.is_valid():
                serializer.save()
                created_items.append(serializer.data)
            else:
                return Response(serializer.errors, status=400)

    return Response({
        "message": f"{len(updated_items)} updated, {len(created_items)} created.",
        "template": {
            "id": template.id,
            "name": template.name,
            "template_type": template.template_type
        },
        "updated_records": updated_items,
        "new_records": created_items
    }, status=200)
    
    
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


