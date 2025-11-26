# Boss_Conn/serializers.py

from rest_framework import serializers


class MigrateRequestSerializer(serializers.Serializer):
    company_id = serializers.IntegerField()
    db         = serializers.DictField(child=serializers.CharField())
