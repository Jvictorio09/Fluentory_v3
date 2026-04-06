from django.db.models import Q

from myApp.models import FeatureFlag, SystemSetting


def is_feature_enabled(key, user=None):
    flag = FeatureFlag.objects.filter(key=key).first()
    if not flag:
        return False
    if not flag.is_enabled:
        return False
    if flag.rollout_percentage <= 0 or user is None:
        return True
    bucket = (user.id or 0) % 100
    return bucket < flag.rollout_percentage


def get_setting(key, default=None):
    row = SystemSetting.objects.filter(key=key).first()
    if not row:
        return default
    try:
        return row.parsed_value()
    except Exception:
        return default


def get_enabled_flags():
    return FeatureFlag.objects.filter(Q(is_enabled=True) | Q(rollout_percentage__gt=0)).values_list('key', flat=True)

