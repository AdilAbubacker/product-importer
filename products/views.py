import os
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from .tasks import import_products_task
from celery.result import AsyncResult
from django.http import JsonResponse

@csrf_exempt
def upload_csv(request):
    if request.method == "POST":
        file = request.FILES["file"]

        # save temp file
        path = os.path.join(settings.MEDIA_ROOT, "upload.csv")
        with open(path, "wb+") as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        # trigger async celery task
        task = import_products_task.delay(path)

        return JsonResponse({"task_id": task.id})

    return JsonResponse({"error": "POST required"}, status=400)




def import_progress(request, task_id):
    result = AsyncResult(task_id)

    if result.state == "PROGRESS":
        return JsonResponse(result.info)

    return JsonResponse({"state": result.state})
