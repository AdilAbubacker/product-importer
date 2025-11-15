from rest_framework import serializers

class ImportCSVSerializer(serializers.Serializer):
    file = serializers.FileField()
