"""
Authentication views for user registration and JWT token management.
"""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authentication.serializers import UserRegisterSerializer, UserSerializer


class UserRegisterView(APIView):
    """
    Public endpoint for registering a new customer account.
    """
    permission_classes = [permissions.AllowAny]

    @extend_schema(
        tags=["Authentication"],
        summary="User registration",
        description="Register a new customer account with unique username and email.",
        request=UserRegisterSerializer,
        responses={
            201: UserSerializer,
            400: OpenApiResponse(description="Validation error or user/email already exists"),
        },
    )
    def post(self, request: Request) -> Response:
        serializer = UserRegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        output_serializer = UserSerializer(user)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
