"""Materiallar va topshiriqlar API'lari."""
from django.db.models import ProtectedError
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .access import visible_assignments, visible_materials
from .models import MaterialFile
from .permissions import IsStaffRoleOrReadOnly
from .serializers import (
    AssignmentSerializer,
    MaterialFileSerializer,
    MaterialFileUploadSerializer,
    MaterialSerializer,
    StudentAssignmentSerializer,
    StudentMaterialSerializer,
)


class MaterialViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffRoleOrReadOnly]

    def get_queryset(self):
        return (
            visible_materials(self.request.user)
            .select_related("author")
            .prefetch_related("groups", "files")
        )

    def get_serializer_class(self):
        if self.request.user.is_student:
            return StudentMaterialSerializer
        return MaterialSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=["post"], parser_classes=[MultiPartParser], url_path="files")
    def upload_file(self, request, pk=None):
        """Materialga fayl biriktirish (multipart, maydon nomi: file)."""
        material = self.get_object()
        serializer = MaterialFileUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["file"]
        material_file = MaterialFile.objects.create(
            material=material,
            file=uploaded_file,
            original_name=uploaded_file.name[:255],
            size=uploaded_file.size,
        )
        return Response(MaterialFileSerializer(material_file).data, status=status.HTTP_201_CREATED)


def get_visible_material_file(user, pk):
    """Faylni faqat uning materialini ko'ra oladigan foydalanuvchiga qaytaradi."""
    return get_object_or_404(
        MaterialFile.objects.select_related("material"),
        pk=pk,
        material__in=visible_materials(user),
    )


class MaterialFileDetailView(APIView):
    """Faylni o'chirish: admin yoki material muallifi."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        if not (request.user.is_admin or request.user.is_teacher):
            raise PermissionDenied("Bu amal faqat admin yoki o'qituvchi uchun.")
        get_visible_material_file(request.user, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MaterialFileDownloadView(APIView):
    """Faylni yuklab olish. Ochiq havola yo'q: har safar token va ruxsat tekshiriladi."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        material_file = get_visible_material_file(request.user, pk)
        try:
            opened_file = material_file.file.open("rb")
        except FileNotFoundError:
            raise NotFound("Fayl serverda topilmadi.")
        return FileResponse(opened_file, as_attachment=True, filename=material_file.original_name)


class AssignmentViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStaffRoleOrReadOnly]

    def get_queryset(self):
        return (
            visible_assignments(self.request.user)
            .select_related("author")
            .prefetch_related("groups")
        )

    def get_serializer_class(self):
        if self.request.user.is_student:
            return StudentAssignmentSerializer
        return AssignmentSerializer

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def perform_destroy(self, instance):
        try:
            instance.delete()
        except ProtectedError:
            raise ValidationError(
                {"detail": "Bu topshiriqqa yechimlar kelgan, shuning uchun uni o'chirib bo'lmaydi."}
            )
