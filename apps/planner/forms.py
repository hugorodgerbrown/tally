"""Forms for the planner: a workout with its ordered items, and an exercise.

Both are bound to the signed-in account: every lookup (the exercises a
workout lists, a name clash, a muscle group) stays inside its library.
"""

import json
import uuid
from typing import Any, cast

from django import forms
from django.contrib.auth.base_user import AbstractBaseUser

from apps.library.models import (
    Equipment,
    Exercise,
    ExerciseType,
    Movement,
    MuscleGroup,
    Workout,
)


class WorkoutForm(forms.ModelForm):
    """Workout settings plus its ordered items, sent by the builder as JSON.

    ``items`` is ``[{"exercise": "<uuid>", "dur": 40}, ...]`` in play order.
    """

    items = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        """Form metadata."""

        model = Workout
        fields = ["name", "description", "rest_seconds", "rounds", "round_rest_seconds"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args: Any, owner: AbstractBaseUser, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.owner = owner

    def clean_items(self) -> list[tuple[Exercise, int]]:
        """Return the items as ``[(exercise, seconds)]``, from the owner's library only."""
        try:
            raw = json.loads(self.cleaned_data["items"])
            wanted = [(uuid.UUID(str(i["exercise"])), int(i["dur"])) for i in raw]
        except (ValueError, TypeError, KeyError) as exc:
            raise forms.ValidationError("The exercise list could not be read.") from exc
        if not wanted:
            raise forms.ValidationError("Add at least one exercise.")
        if any(not 5 <= dur <= 3600 for _, dur in wanted):
            raise forms.ValidationError("Each exercise needs between 5 and 3600 seconds.")
        exercises = Exercise.objects.for_user(self.owner).in_bulk(
            [u for u, _ in wanted], field_name="uuid"
        )
        if {u for u, _ in wanted} - set(exercises):
            raise forms.ValidationError("An exercise in the list no longer exists.")
        return [(exercises[u], dur) for u, dur in wanted]


class ExerciseForm(forms.ModelForm):
    """An exercise, with its types, muscles and any new muscle groups to add."""

    types = forms.ModelMultipleChoiceField(
        queryset=ExerciseType.objects.all(),
        to_field_name="slug",
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Pick at least one type."},
    )
    muscles = forms.ModelMultipleChoiceField(
        queryset=MuscleGroup.objects.none(),
        to_field_name="uuid",
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    new_muscles = forms.CharField(
        required=False,
        label="Other muscles",
        help_text="Comma separated, for muscles not listed above.",
    )

    class Meta:
        """Form metadata."""

        model = Exercise
        fields = [
            "name",
            "types",
            "muscles",
            "movement",
            "equipment",
            "one_sided",
            "default_duration",
            "description",
        ]
        labels = {
            "equipment": "Equipment",
            "movement": "Movement",
            "one_sided": "Runs per side",
            "default_duration": "Default duration",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "equipment": forms.RadioSelect,
            "movement": forms.RadioSelect,
        }

    def __init__(self, *args: Any, owner: AbstractBaseUser, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.owner = owner
        muscles = cast(forms.ModelMultipleChoiceField, self.fields["muscles"])
        muscles.queryset = MuscleGroup.objects.visible_to(owner)
        equipment = cast(forms.ChoiceField, self.fields["equipment"])
        equipment.choices = [("", "None"), *Equipment.choices]
        # Older pages post nothing: keep what the exercise already has (the
        # model default, dynamic, for a new one) rather than an error.
        self.fields["movement"].required = False

    def clean_movement(self) -> str:
        """Return the posted movement, or the exercise's current one when none was sent."""
        return self.cleaned_data.get("movement") or self.instance.movement or Movement.DYNAMIC

    def clean_name(self) -> str:
        """Return the trimmed name; refuse one the owner's library already has (any case)."""
        name: str = self.cleaned_data["name"].strip()
        clash = (
            Exercise.objects.for_user(self.owner)
            .filter(name__iexact=name)
            .exclude(pk=self.instance.pk)
        )
        if clash.exists():
            raise forms.ValidationError("An exercise with this name already exists.")
        return name

    def clean_new_muscles(self) -> list[str]:
        """Return the extra muscle names, trimmed and capitalised."""
        names = [n.strip() for n in self.cleaned_data["new_muscles"].split(",")]
        return [n[:1].upper() + n[1:] for n in names if n]

    def save(self, commit: bool = True) -> Exercise:
        """Save the exercise as the owner's, then add any new muscle groups to it."""
        self.instance.owner = self.owner
        exercise: Exercise = super().save(commit=commit)
        if commit:
            extra = [
                MuscleGroup.objects.named(self.owner, n) for n in self.cleaned_data["new_muscles"]
            ]
            exercise.muscles.add(*extra)
        return exercise
