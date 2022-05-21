# -*- coding: utf-8 -*-

# This file is part of wger Workout Manager.
#
# wger Workout Manager is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# wger Workout Manager is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with Workout Manager.  If not, see <http://www.gnu.org/licenses/>.

# Standard Library
import logging

# Django
from django.db.models import Q
from django.utils.translation import gettext as _

# Third Party
from actstream import action as actstream_action
from easy_thumbnails.alias import aliases
from easy_thumbnails.files import get_thumbnailer
from rest_framework import viewsets
from rest_framework.decorators import (
    action,
    api_view,
)
from rest_framework.response import Response

# wger
from wger.exercises.views.helper import HistoryModes
from wger.config.models import LanguageConfig
from wger.core.api.viewsets import CreateUpdateModelViewSet
from wger.exercises.api.permissions import CanEditExercises
from wger.exercises.api.serializers import (
    ExerciseTranslationSerializer,
    EquipmentSerializer,
    ExerciseAliasSerializer,
    ExerciseBaseInfoSerializer,
    ExerciseBaseSerializer,
    ExerciseCategorySerializer,
    ExerciseCommentSerializer,
    ExerciseImageSerializer,
    ExerciseInfoSerializer,
    ExerciseSerializer,
    ExerciseVariationSerializer,
    ExerciseVideoSerializer,
    MuscleSerializer,
)
from wger.exercises.models import (
    Alias,
    Equipment,
    Exercise,
    ExerciseBase,
    ExerciseCategory,
    ExerciseComment,
    ExerciseImage,
    ExerciseVideo,
    Muscle,
    Variation,
)
from wger.utils.language import load_item_languages


logger = logging.getLogger(__name__)


class ExerciseBaseViewSet(CreateUpdateModelViewSet):
    """
    API endpoint for exercise base objects. For a read-only endpoint with all
    the information of an exercise, see /api/v2/exerciseinfo/
    """
    queryset = ExerciseBase.objects.all()
    serializer_class = ExerciseBaseSerializer
    permission_classes = (CanEditExercises, )
    ordering_fields = '__all__'
    filterset_fields = (
        'category',
        'muscles',
        'muscles_secondary',
        'equipment',
    )

    def perform_create(self, serializer):
        """
        Save entry to activity stream
        """
        super().perform_create(serializer)
        actstream_action.send(self.request.user, verb='created', action_object=serializer.instance)

    def perform_update(self, serializer):
        """
        Save entry to activity stream
        """
        super().perform_create(serializer)
        actstream_action.send(self.request.user, verb='updated', action_object=serializer.instance)


class ExerciseTranslationViewSet(CreateUpdateModelViewSet):
    """
    API endpoint for editing or adding exercise objects.
    """
    queryset = Exercise.objects.all()
    permission_classes = (CanEditExercises, )
    serializer_class = ExerciseTranslationSerializer
    ordering_fields = '__all__'
    filterset_fields = (
        'uuid',
        'creation_date',
        'exercise_base',
        'description',
        'name',
    )

    def perform_create(self, serializer):
        """
        Save entry to activity stream
        """
        super().perform_create(serializer)
        actstream_action.send(
            self.request.user,
            verb=HistoryModes.CREATED.value,
            action_object=serializer.instance,
        )

    def perform_update(self, serializer):
        """
        Save entry to activity stream
        """
        super().perform_create(serializer)
        actstream_action.send(
            self.request.user,
            verb=HistoryModes.UPDATED.value,
            action_object=serializer.instance,
        )


class ExerciseViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for exercise objects. For a single read-only endpoint with all
    the information of an exercise, see /api/v2/exerciseinfo/
    """
    queryset = Exercise.objects.all()
    permission_classes = (CanEditExercises, )
    serializer_class = ExerciseSerializer
    ordering_fields = '__all__'
    filterset_fields = (
        'uuid',
        'creation_date',
        'exercise_base',
        'description',
        'language',
        'name',
    )

    def get_queryset(self):
        """Add additional filters for fields from exercise base"""

        qs = Exercise.objects.all()

        category = self.request.query_params.get('category')
        muscles = self.request.query_params.get('muscles')
        muscles_secondary = self.request.query_params.get('muscles_secondary')
        equipment = self.request.query_params.get('equipment')
        license = self.request.query_params.get('license')

        if category:
            try:
                qs = qs.filter(exercise_base__category_id=int(category))
            except ValueError:
                logger.info(f"Got {category} as category ID")

        if muscles:
            try:
                qs = qs.filter(exercise_base__muscles__in=[int(m) for m in muscles.split(',')])
            except ValueError:
                logger.info(f"Got {muscles} as muscle IDs")

        if muscles_secondary:
            try:
                muscle_ids = [int(m) for m in muscles_secondary.split(',')]
                qs = qs.filter(exercise_base__muscles_secondary__in=muscle_ids)
            except ValueError:
                logger.info(f"Got '{muscles_secondary}' as secondary muscle IDs")

        if equipment:
            try:
                qs = qs.filter(exercise_base__equipment__in=[int(e) for e in equipment.split(',')])
            except ValueError:
                logger.info(f"Got {equipment} as equipment IDs")

        if license:
            try:
                qs = qs.filter(exercise_base__license_id=int(license))
            except ValueError:
                logger.info(f"Got {license} as license ID")

        return qs


@api_view(['GET'])
def search(request):
    """
    Searches for exercises.

    This format is currently used by the exercise search autocompleter
    """
    q = request.GET.get('term', None)
    results = []
    json_response = {}

    if q:
        languages = load_item_languages(
            LanguageConfig.SHOW_ITEM_EXERCISES, language_code=request.GET.get('language', None)
        )
        name_lookup = Q(name__icontains=q) | Q(alias__alias__icontains=q)
        exercises = (
            Exercise.objects.filter(name_lookup).all().filter(
                language__in=languages
            ).order_by('exercise_base__category__name', 'name').distinct()
        )

        for exercise in exercises:
            if exercise.main_image:
                image_obj = exercise.main_image
                image = image_obj.image.url
                t = get_thumbnailer(image_obj.image)
                thumbnail = t.get_thumbnail(aliases.get('micro_cropped')).url
            else:
                image = None
                thumbnail = None

            exercise_json = {
                'value': exercise.name,
                'data': {
                    'id': exercise.id,
                    'name': exercise.name,
                    'category': _(exercise.category.name),
                    'image': image,
                    'image_thumbnail': thumbnail
                }
            }
            results.append(exercise_json)
        json_response['suggestions'] = results

    return Response(json_response)


class ExerciseInfoViewset(viewsets.ReadOnlyModelViewSet):
    """
    Read-only info API endpoint for exercise objects. Returns nested data
    structures for more easy parsing.
    """

    queryset = Exercise.objects.all()
    serializer_class = ExerciseInfoSerializer
    ordering_fields = '__all__'
    filterset_fields = (
        'creation_date',
        'description',
        'name',
        'exercise_base',
        'license',
        'license_author',
    )


class ExerciseBaseInfoViewset(viewsets.ReadOnlyModelViewSet):
    """
    Read-only info API endpoint for exercise objects, grouped by the exercise
    base. Returns nested data structures for more easy and faster parsing.
    """

    queryset = ExerciseBase.objects.all()
    serializer_class = ExerciseBaseInfoSerializer
    ordering_fields = '__all__'
    filterset_fields = (
        'category',
        'muscles',
        'muscles_secondary',
        'equipment',
        'variations',
        'license',
        'license_author',
    )


class EquipmentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for equipment objects
    """
    queryset = Equipment.objects.all()
    serializer_class = EquipmentSerializer
    ordering_fields = '__all__'
    filterset_fields = ('name', )


class ExerciseCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for exercise categories objects
    """
    queryset = ExerciseCategory.objects.all()
    serializer_class = ExerciseCategorySerializer
    ordering_fields = '__all__'
    filterset_fields = ('name', )


class ExerciseImageViewSet(CreateUpdateModelViewSet):
    """
    API endpoint for exercise image objects
    """

    queryset = ExerciseImage.objects.all()
    serializer_class = ExerciseImageSerializer
    permission_classes = (CanEditExercises, )
    ordering_fields = '__all__'
    filterset_fields = (
        'is_main',
        'status',
        'exercise_base',
        'license',
        'license_author',
    )

    @action(detail=True)
    def thumbnails(self, request, pk):
        """
        Return a list of the image's thumbnails
        """
        try:
            image = ExerciseImage.objects.get(pk=pk)
        except ExerciseImage.DoesNotExist:
            return Response([])

        thumbnails = {}
        for alias in aliases.all():
            t = get_thumbnailer(image.image)
            thumbnails[alias] = {
                'url': t.get_thumbnail(aliases.get(alias)).url,
                'settings': aliases.get(alias)
            }
        thumbnails['original'] = image.image.url
        return Response(thumbnails)

    def perform_create(self, serializer):
        """
        Save entry to activity stream
        """
        super().perform_create(serializer)
        actstream_action.send(
            self.request.user,
            verb=HistoryModes.CREATED.value,
            action_object=serializer.instance,
        )

    def perform_update(self, serializer):
        """
        Save entry to activity stream
        """
        super().perform_create(serializer)
        actstream_action.send(
            self.request.user,
            verb=HistoryModes.UPDATED.value,
            action_object=serializer.instance,
        )


class ExerciseVideoViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for exercise video objects
    """
    queryset = ExerciseVideo.objects.all()
    serializer_class = ExerciseVideoSerializer
    ordering_fields = '__all__'
    filterset_fields = (
        'is_main',
        'exercise_base',
        'license',
        'license_author',
    )


class ExerciseCommentViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for exercise comment objects
    """
    serializer_class = ExerciseCommentSerializer
    permission_classes = (CanEditExercises, )
    ordering_fields = '__all__'
    filterset_fields = ('comment', 'exercise')

    def get_queryset(self):
        """Filter by language for exercise comments"""
        qs = ExerciseComment.objects.all()
        language = self.request.query_params.get('language')
        if language:
            exercises = Exercise.objects.filter(language=language)
            qs = ExerciseComment.objects.filter(exercise__in=exercises)
        return qs

    def perform_create(self, serializer):
        """
        Save entry to activity stream
        """
        super().perform_create(serializer)
        actstream_action.send(
            self.request.user,
            verb=HistoryModes.CREATED.value,
            action_object=serializer.instance,
        )

    def perform_update(self, serializer):
        """
        Save entry to activity stream
        """
        super().perform_create(serializer)
        actstream_action.send(
            self.request.user,
            verb=HistoryModes.UPDATED.value,
            action_object=serializer.instance,
        )


class ExerciseAliasViewSet(CreateUpdateModelViewSet):
    """
    API endpoint for exercise aliases objects
    """
    serializer_class = ExerciseAliasSerializer
    queryset = Alias.objects.all()
    permission_classes = (CanEditExercises, )
    ordering_fields = '__all__'
    filterset_fields = ('alias', 'exercise')


class ExerciseVariationViewSet(CreateUpdateModelViewSet):
    """
    API endpoint for exercise variation objects
    """
    serializer_class = ExerciseVariationSerializer
    queryset = Variation.objects.all()
    permission_classes = (CanEditExercises, )


class MuscleViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for muscle objects
    """
    queryset = Muscle.objects.all()
    serializer_class = MuscleSerializer
    ordering_fields = '__all__'
    filterset_fields = ('name', 'is_front')
