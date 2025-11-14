import random, string
from rest_framework.decorators import api_view, permission_classes
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework.response import Response
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
from .models import UserProfile, UserRole
from Paymagics_Payor.models import Payee, Category
from Paymagics_Payor.serializers import PayeeSerializer, CategorySerializer
from .serializers import CreatePayorSerializer, UserProfileSerializer, CreatePayorStaffSerializer, PasswordResetConfirmSerializer, PasswordResetRequestSerializer
from django.contrib.auth.hashers import make_password
from Paymagics_PayorStaff.models import  PaymentTemplate
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import send_mail
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.conf import settings
from django.db.models import Q

# ---------------------- LOGIN SECTION ----------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    username = request.data.get("username")
    password = request.data.get("password")

    user = authenticate(username=username, password=password)
    if not user:
        return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

    role = None
    payor_id = None

    if user.is_superuser or user.is_staff:
        role = "admin"
        user_profile = None
    else:
        try:
            user_profile = UserProfile.objects.get(user=user)
        except UserProfile.DoesNotExist:
            return Response({"error": "User profile not found"}, status=status.HTTP_404_NOT_FOUND)

        if not user_profile.is_confirmed:
            return Response({"error": "Account not confirmed by admin"}, status=status.HTTP_403_FORBIDDEN)

        if not user_profile.is_otp_verified:
            return Response({"error": "OTP not verified"}, status=status.HTTP_403_FORBIDDEN)

        role = user_profile.role

        if role == UserRole.PAYOR:
            payor_id = user_profile.id

        if role == UserRole.PAYOR_STAFF and user_profile.created_by:
            payor_id = user_profile.created_by.id

    refresh = RefreshToken.for_user(user)

    profile_data = UserProfileSerializer(user_profile).data if user_profile else None

    return Response({
        "refresh": str(refresh),
        "access": str(refresh.access_token),
        "username": user.username,
        "email": user.email,
        "role": role,
        "payor_id": payor_id,
        "is_superuser": user.is_superuser,
        "is_staff": user.is_staff,
        "profile": profile_data,  
    }, status=status.HTTP_200_OK)
    
# -----------------------logout-----------------------
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    try:
        refresh_token = request.data.get("refresh")
        token = RefreshToken(refresh_token)
        token.blacklist() 
        return Response({"message": "Successfully logged out"}, status=status.HTTP_200_OK)
    except TokenError:
        return Response({"error": "Invalid or expired token"}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    

# ---------------------------- SIGNUP ------------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def signup(request):
    firstname = request.data.get("firstname")
    lastname = request.data.get("lastname")
    username = request.data.get("username")
    email = request.data.get("email")
    password = request.data.get("password")
    mobile = request.data.get("mobile")

    if not all([firstname, lastname, email, password, mobile]):
        return Response(
            {"error": "Firstname, lastname, email, password, and mobile are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
        
    if not username:
        username = email.split("@")[0] + str(random.randint(1000, 9999))

    if User.objects.filter(username=username).exists():
        return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)

    if User.objects.filter(email=email).exists():
        return Response({"error": "Email already exists"}, status=status.HTTP_400_BAD_REQUEST)

    referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    user = User.objects.create(
        username=username,
        email=email,
        first_name=firstname or "",
        last_name=lastname or "",
        password=make_password(password),
    )

    UserProfile.objects.create(
        user=user,
        first_name=firstname or "",
        last_name=lastname or "",
        username=username,
        email=email,
        mobile=mobile,
        referral_code=referral_code,
        role=UserRole.PAYOR,
        is_otp_verified=True,
    )

    return Response(
        {
            "message": "Signup successful. Waiting for admin approval.",
            "user": {
                "firstname": firstname,
                "lastname": lastname,
                "username": username,
                "email": email,
                "mobile": mobile,
                "referral_code": referral_code,
                "role": "PAYOR"
            }
        },
        status=status.HTTP_201_CREATED
    )
    
# ---------------------------- PASSWORD RESET ----------------------------
@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_request(request):
    serializer = PasswordResetRequestSerializer(data=request.data)
    if serializer.is_valid():
        email = serializer.validated_data["email"]
        user = User.objects.get(email=email)

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = PasswordResetTokenGenerator().make_token(user)

        reset_link = f"{settings.FRONTEND_URL}/reset-password/{uidb64}/{token}/"

        send_mail(
            subject="Password Reset Request",
            message=f"Click the link to reset your password: {reset_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
        )

        return Response(
            {"message": "Password reset link sent to your email."},
            status=status.HTTP_200_OK,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def password_reset_confirm(request):
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {"message": "Password has been reset successfully."},
            status=status.HTTP_200_OK,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# ---------------------------- LIST UNAPPROVED PAYORS ------------------------
@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_unapproved_payors(request):
    unapproved = UserProfile.objects.filter(role=UserRole.PAYOR, is_confirmed=False)

    if not unapproved.exists():
        return Response(
            {"message": "No new unapproved payors"},
            status=status.HTTP_200_OK
        )

    data = [
        {
            "id": p.id,
            "first_name": p.first_name,
            "last_name": p.last_name,
            "username": p.username,
            "email": p.email,
            "mobile": p.mobile,
            "referral_code": p.referral_code,
            "is_confirmed": p.is_confirmed,
        }
        for p in unapproved
    ]

    return Response(data, status=status.HTTP_200_OK)


# ---------------------------- APPROVE PAYOR ------------------------
@api_view(["POST"])
@permission_classes([IsAdminUser])
def approve_payor(request, pk):
    payor = get_object_or_404(UserProfile, id=pk, role=UserRole.PAYOR)
    payor.is_confirmed = True
    payor.save()

    subject = "Signup verification completed"
    message = (
        f"Hello {payor.first_name},\n\n"
        f"Your account verification is successfully completed.\n\n"
        "Thank you!"
    )

    return Response({"message": "Payor approved successfully"}, status=status.HTTP_200_OK)


# ---------------------- PAYOR SECTION ----------------------
@api_view(["POST"])
@permission_classes([IsAdminUser])
def create_payor(request):
    serializer = CreatePayorSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data["username"]
        email = serializer.validated_data["email"]

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists."}, status=400)
        if User.objects.filter(email=email).exists():
            return Response({"error": "Email already exists."}, status=400)

        user = User.objects.create_user(
            username=username,
            password=serializer.validated_data["password"],
            email=email,
            first_name=serializer.validated_data["first_name"],
            last_name=serializer.validated_data["last_name"],
        )

        referral_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # Safe version
        profile, _ = UserProfile.objects.get_or_create(user=user)

        profile.username = user.username
        profile.email = user.email
        profile.first_name = user.first_name
        profile.last_name = user.last_name
        profile.mobile = serializer.validated_data["mobile"]
        profile.role = UserRole.PAYOR
        profile.referral_code = referral_code
        profile.is_confirmed = True
        profile.is_otp_verified = True
        profile.save()

        return Response(UserProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from rest_framework.pagination import PageNumberPagination


@api_view(["GET"])
@permission_classes([IsAdminUser])
def list_payors(request):
    queryset = UserProfile.objects.filter(
        role=UserRole.PAYOR,
        user__is_active=True, 
        is_confirmed=True
    )

    total_count = queryset.count()  # 👈 Get total number of payors

    paginator = PageNumberPagination()
    paginator.page_size = 15 
    paginated_queryset = paginator.paginate_queryset(queryset, request)

    serializer = UserProfileSerializer(paginated_queryset, many=True)

    response = paginator.get_paginated_response(serializer.data)
    response.data["total_count"] = total_count  # 👈 Add total count to response
    return response




@api_view(["PUT", "PATCH"])
@permission_classes([IsAdminUser])
def update_payor(request, pk):
    profile = get_object_or_404(UserProfile, pk=pk, role=UserRole.PAYOR)
    user = profile.user

    serializer = CreatePayorSerializer(data=request.data, partial=True)
    if serializer.is_valid():
        data = serializer.validated_data
        if "username" in data: user.username = data["username"]
        if "email" in data: user.email = data["email"]
        if "first_name" in data: user.first_name = data["first_name"]
        if "last_name" in data: user.last_name = data["last_name"]
        if "password" in data: user.set_password(data["password"])
        user.save()

        profile.username = user.username
        profile.email = user.email
        profile.first_name = user.first_name
        profile.last_name = user.last_name
        if "mobile" in data: profile.mobile = data["mobile"]
        profile.save()

        return Response(UserProfileSerializer(profile).data, status=200)
    return Response(serializer.errors, status=400)


@api_view(["DELETE"])
@permission_classes([IsAdminUser])
def delete_payor(request, pk):
    profile = get_object_or_404(UserProfile, pk=pk, role=UserRole.PAYOR)
    # instead of deleting, set inactive
    profile.user.is_active = False
    profile.user.save(update_fields=["is_active"])
    return Response({"detail": "Payor deactivated successfully"}, status=200)


# ---------------------- PAYOR STAFF SECTION ----------------------
@api_view(["POST"])
@permission_classes([IsAdminUser])
def create_payor_staff(request):
    serializer = CreatePayorStaffSerializer(data=request.data)
    if serializer.is_valid():
        username = serializer.validated_data["username"]
        email = serializer.validated_data["email"]

        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already exists."}, status=400)
        if User.objects.filter(email=email).exists():
            return Response({"error": "Email already exists."}, status=400)

        user = User.objects.create_user(
            username=username,
            password=serializer.validated_data["password"],
            email=email,
            first_name=serializer.validated_data["first_name"],
            last_name=serializer.validated_data["last_name"],
        )

        # Safe way: reuse if signal already created it
        profile, _ = UserProfile.objects.get_or_create(user=user)

        profile.username = user.username
        profile.email = user.email
        profile.first_name = user.first_name
        profile.last_name = user.last_name
        profile.mobile = serializer.validated_data["mobile"]
        profile.role = UserRole.PAYOR_STAFF
        profile.is_confirmed = True
        profile.is_otp_verified = True
        profile.save()

        return Response(UserProfileSerializer(profile).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


from rest_framework.pagination import PageNumberPagination

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_payor_staff(request):
    queryset = UserProfile.objects.filter(
        role=UserRole.PAYOR_STAFF,
        user__is_active=True
    )

    total_count = queryset.count()  # Get total number of staff

    paginator = PageNumberPagination()
    paginator.page_size = 10  
    paginated_queryset = paginator.paginate_queryset(queryset, request)

    serializer = UserProfileSerializer(paginated_queryset, many=True)

    response = paginator.get_paginated_response(serializer.data)
    response.data["total_count"] = total_count  # Add total count to response
    return response




@api_view(["PUT"])
@permission_classes([IsAuthenticated])
def edit_payor_staff(request, pk):
    profile = get_object_or_404(UserProfile, pk=pk, role=UserRole.PAYOR_STAFF)
    serializer = UserProfileSerializer(profile, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=200)
    return Response(serializer.errors, status=400)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_payor_staff(request, pk):
    profile = get_object_or_404(UserProfile, pk=pk, role=UserRole.PAYOR_STAFF)
    # Soft delete: mark user inactive
    profile.user.is_active = False
    profile.user.save(update_fields=["is_active"])
    return Response({"detail": "Payor Staff deactivated successfully"}, status=200)


# ---------------------- ADMIN DASHBOARD ----------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_dashboard(request):
    total_payors = UserProfile.objects.filter(role=UserRole.PAYOR, user__is_active=True).count()
    total_payor_staff = UserProfile.objects.filter(role=UserRole.PAYOR_STAFF, user__is_active=True).count()
    total_payees = Payee.objects.filter(is_active=True).count()

    active_users = UserProfile.objects.filter(user__is_active=True).count()
    inactive_users = UserProfile.objects.filter(user__is_active=False).count()

    confirmed_users = UserProfile.objects.filter(is_confirmed=True).count()
    not_confirmed_users = UserProfile.objects.filter(is_confirmed=False).count()

    otp_verified_users = UserProfile.objects.filter(is_otp_verified=True).count()
    otp_not_verified_users = UserProfile.objects.filter(is_otp_verified=False).count()

    active_sessions = Session.objects.filter(expire_date__gte=timezone.now()).count()

    system_start = (
        UserProfile.objects.earliest("created_at").created_at
        if UserProfile.objects.exists()
        else timezone.now()
    )
    uptime_days = (timezone.now() - system_start).days

    try:
        last_payroll = PaymentTemplate.objects.order_by("-created_at").first()
    except Exception:
        last_payroll = None

    new_employee = UserProfile.objects.order_by("-created_at").first()

    recent_activity = {
        "last_payroll": getattr(last_payroll, "description", None),
        "new_employee_added": getattr(new_employee, "username", None),
    }

    data = {
        "counts": {
            "payors": total_payors,
            "payor_staff": total_payor_staff,
            "payees": total_payees,
            "total_users": total_payors + total_payor_staff + total_payees,
        },
        "status_breakdown": {
            "active": active_users,
            "inactive": inactive_users,
        },
        "confirmation_status": {
            "confirmed": confirmed_users,
            "not_confirmed": not_confirmed_users,
        },
        "otp_status": {
            "otp_verified": otp_verified_users,
            "otp_not_verified": otp_not_verified_users,
        },
        "system_overview": {
            "active_sessions": active_sessions,
            "uptime_days": uptime_days,
        },
        "recent_activity": recent_activity,
    }

    return Response(data, status=200)


# ------------------------ search users
@api_view(["GET"])
@permission_classes([AllowAny])
def search_categories(request):
    query = request.GET.get("q", "")
    categories = Category.objects.filter(
        Q(category__icontains=query)
    )
    serializer = CategorySerializer(categories, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def search_payees(request):
    query = request.GET.get("q", "")
    payees = Payee.objects.filter(
        Q(ben_code__icontains=query) |
        Q(ben_name__icontains=query) |
        Q(city__icontains=query) |
        Q(state__icontains=query) |
        Q(contact__icontains=query) |
        Q(email__icontains=query) |
        Q(bank_name__icontains=query) |
        Q(branch__icontains=query)
    ).distinct()
    serializer = PayeeSerializer(payees, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def search_payors(request):
    query = request.GET.get("q", "")
    users = UserProfile.objects.filter(
        role=UserRole.PAYOR
    ).filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query) |
        Q(mobile__icontains=query)
    ).distinct()

    serializer = UserProfileSerializer(users, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([AllowAny])
def search_payor_staff(request):
    query = request.GET.get("q", "")
    users = UserProfile.objects.filter(
        role=UserRole.PAYOR_STAFF
    ).filter(
        Q(username__icontains=query) |
        Q(first_name__icontains=query) |
        Q(last_name__icontains=query) |
        Q(email__icontains=query) |
        Q(mobile__icontains=query)
    ).distinct()

    serializer = UserProfileSerializer(users, many=True)
    return Response(serializer.data)


# ---------------------------- PROFILE ------------------------
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_profile(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
 
    serializer = UserProfileSerializer(profile)
    return Response(serializer.data, status=status.HTTP_200_OK)
 
 
@api_view(["PUT", "PATCH"])
@permission_classes([IsAuthenticated])
def update_profile(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        return Response({"error": "Profile not found"}, status=status.HTTP_404_NOT_FOUND)
 
    serializer = UserProfileSerializer(profile, data=request.data, partial=True)
 
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
 
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)