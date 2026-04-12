from django.utils import timezone


def now_processor(request):
    return {'now': timezone.localtime(timezone.now())}