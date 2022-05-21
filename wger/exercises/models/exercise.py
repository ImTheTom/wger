#  This file is part of wger Workout Manager <https://github.com/wger-project>.
#  Copyright (C) 2013 - 2021 wger Team
#
#  wger Workout Manager is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  wger Workout Manager is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Standard Library
import uuid

# Django
from django.conf import settings
from django.contrib.auth.models import User
from django.contrib.sites.models import Site
from django.core import mail
from django.core.validators import MinLengthValidator
from django.db import models
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import translation
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _

# Third Party
import bleach
from actstream import action
from simple_history.models import HistoricalRecords

# wger
from wger.core.models import Language
from wger.exercises.models import ExerciseBase
from wger.utils.cache import (
    delete_template_fragment_cache,
    reset_workout_canonical_form,
)
from wger.utils.models import AbstractLicenseModel


class Exercise(AbstractLicenseModel, models.Model):
    """
    Model for an exercise
    """
    description = models.TextField(
        max_length=2000,
        verbose_name=_('Description'),
        validators=[MinLengthValidator(40)],
    )
    """Description on how to perform the exercise"""

    name = models.CharField(
        max_length=200,
        verbose_name=_('Name'),
    )
    """The exercise's name"""

    creation_date = models.DateField(
        _('Date'),
        auto_now_add=True,
        null=True,
        blank=True,
    )
    """The submission date"""

    update_date = models.DateTimeField(_('Date'), auto_now=True)
    """Datetime of the last modification"""

    language = models.ForeignKey(
        Language,
        verbose_name=_('Language'),
        on_delete=models.CASCADE,
    )
    """The exercise's language"""

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        verbose_name='UUID',
    )
    """Globally unique ID, to identify the exercise across installations"""

    exercise_base = models.ForeignKey(
        ExerciseBase,
        verbose_name='ExerciseBase',
        on_delete=models.CASCADE,
        default=None,
        null=True,
        related_name='exercises',
    )
    """ Refers to the base exercise with non translated information """

    history = HistoricalRecords()
    """Edit history"""

    #
    # Django methods
    #
    class Meta:
        base_manager_name = 'objects'
        ordering = [
            "name",
        ]

    def get_absolute_url(self):
        """
        Returns the canonical URL to view an exercise
        """
        return reverse('exercise:exercise:view', kwargs={'id': self.id, 'slug': slugify(self.name)})

    def save(self, *args, **kwargs):
        """
        Reset all cached infos
        """
        super(Exercise, self).save(*args, **kwargs)

        # Cached template fragments
        for language in Language.objects.all():
            delete_template_fragment_cache('muscle-overview', language.id)
            delete_template_fragment_cache('exercise-overview', language.id)
            delete_template_fragment_cache('equipment-overview', language.id)

        # Cached workouts
        for setting in self.exercise_base.setting_set.all():
            reset_workout_canonical_form(setting.set.exerciseday.training_id)

    def delete(self, *args, **kwargs):
        """
        Reset all cached infos
        """

        # Cached template fragments
        for language in Language.objects.all():
            delete_template_fragment_cache('muscle-overview', language.id)
            delete_template_fragment_cache('exercise-overview', language.id)
            delete_template_fragment_cache('equipment-overview', language.id)

        # Cached workouts
        for setting in self.exercise_base.setting_set.all():
            reset_workout_canonical_form(setting.set.exerciseday.training.pk)

        super(Exercise, self).delete(*args, **kwargs)

    def __str__(self):
        """
        Return a more human-readable representation
        """
        return self.name

    #
    # Properties to expose the info from the exercise base
    #
    @property
    def category(self):
        return self.exercise_base.category

    @property
    def muscles(self):
        return self.exercise_base.muscles

    @property
    def muscles_secondary(self):
        return self.exercise_base.muscles_secondary

    @property
    def equipment(self):
        return self.exercise_base.equipment

    @property
    def images(self):
        return self.exercise_base.exerciseimage_set

    @property
    def videos(self):
        return self.exercise_base.exercisevideo_set

    @property
    def variations(self):
        """
        Returns the variations for this exercise in the same language
        """
        out = []
        if self.exercise_base.variations:
            for variation in self.exercise_base.variations.exercisebase_set.all():
                for exercise in variation.exercises.filter(language=self.language).all():
                    out.append(exercise)
        return out

    #
    # Own methods
    #
    @property
    def main_image(self):
        """
        Return the main image for the exercise or None if nothing is found
        """
        return self.images.accepted().filter(is_main=True).first()

    @property
    def description_clean(self):
        """
        Return the exercise description with all markup removed
        """
        return bleach.clean(self.description, strip=True)

    def get_owner_object(self):
        """
        Exercise has no owner information
        """
        return False

    def send_email(self, request):
        """
        Sends an email after being successfully added to the database (for user
        submitted exercises only)
        """
        try:
            user = User.objects.get(username=self.license_author)
        except User.DoesNotExist:
            return
        if self.license_author and user.email:
            translation.activate(user.userprofile.notification_language.short_name)
            url = request.build_absolute_uri(self.get_absolute_url())
            subject = _('Exercise was successfully added to the general database')
            context = {
                'exercise': self.name,
                'url': url,
                'site': Site.objects.get_current().domain,
            }
            message = render_to_string('exercise/email_new.tpl', context)
            mail.send_mail(
                subject,
                message,
                settings.WGER_SETTINGS['EMAIL_FROM'], [user.email],
                fail_silently=True
            )

    def set_author(self, request):
        """
        Set author
        This is only used when creating exercises (via web or API)
        """

        if request.user.has_perm('exercises.add_exercise'):
            if not self.license_author:
                self.license_author = request.get_host().split(':')[0]
        else:
            if not self.license_author:
                self.license_author = request.user.username

            subject = _('New user submitted exercise')

            message = _('The user {0} submitted a new exercise "{1}".'
                        ).format(request.user.username, self.name)
            mail.mail_admins(
                str(subject),
                str(message),
                fail_silently=True,
            )
