from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from Paymagics_Admin.models import *
from .models import Bank
from .serializers import BankSerializer
from django.db.models import Q
from rest_framework.pagination import PageNumberPagination

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_banks(request):
    banks = Bank.objects.filter(is_active=True).order_by('-id')

    paginator = PageNumberPagination()
    paginator.page_size = 15
    paginated_banks = paginator.paginate_queryset(banks, request)

    serializer = BankSerializer(paginated_banks, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_bank(request):
    serializer = BankSerializer(data=request.data)
    if serializer.is_valid():
        usr = UserProfile.objects.get(user=request.user)
        serializer.save(creator= usr) 
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_bank(request, pk):
    try:
        bank = Bank.objects.get(pk=pk, is_active=True)
    except Bank.DoesNotExist:
        return Response({"error": "Bank not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = BankSerializer(bank)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def update_bank(request, pk):
    try:
        bank = Bank.objects.get(pk=pk, is_active=True)
    except Bank.DoesNotExist:
        return Response({"error": "Bank not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = BankSerializer(bank, data=request.data, partial=True)

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_bank(request, pk):
    try:
        bank = Bank.objects.get(pk=pk, is_active=True)
    except Bank.DoesNotExist:
        return Response({"error": "Bank not found"}, status=status.HTTP_404_NOT_FOUND)

    # Soft delete (set is_active = False)
    bank.is_active = False
    bank.save()
    return Response({"message": "Bank deleted successfully"}, status=status.HTTP_200_OK)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def filter_banks_by_type(request):
    acc_type = request.query_params.get('type')

    if not acc_type:
        return Response({"error": "Account type is required (use ?type=TYPE)"}, status=400)

    banks = Bank.objects.filter(acc_type__iexact=acc_type, is_active=True)
    serializer = BankSerializer(banks, many=True)
    return Response(serializer.data, status=200)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_banks(request):
    query = request.query_params.get('q', '').strip()

    if not query:
        return Response({"error": "Search query is required (use ?q=SEARCH_TERM)"}, status=400)

    banks = Bank.objects.filter(
        Q(bank_name__icontains=query) |
        Q(acc_type__icontains=query) |
        Q(acc_no__icontains=query) |
        Q(ifsc__icontains=query) |
        Q(branch__icontains=query) |
        Q(acc_holder__icontains=query) |
        Q(mobile__icontains=query) |
        Q(email__icontains=query),
        is_active=True
    )

    serializer = BankSerializer(banks, many=True)
    return Response(serializer.data, status=200)