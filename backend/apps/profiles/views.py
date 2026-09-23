from rest_framework import permissions, viewsets
from rest_framework.parsers import FormParser, MultiPartParser

from .models import ProfileSet
from .serializers import ProfileSetSerializer


class ProfileSetViewSet(viewsets.ModelViewSet):
    """
    GET/POST /api/profile-sets/, GET/PUT/PATCH/DELETE /api/profile-sets/<id>/
    — CRUD над сетами профиля (контакты + резюме) текущего пользователя.
    MultiPartParser нужен для загрузки файла резюме через multipart/form-data.
    """

    serializer_class = ProfileSetSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return ProfileSet.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
