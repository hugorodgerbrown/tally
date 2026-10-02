import json
import uuid

from django import forms

from library.models import Exercise, ExerciseType, MuscleGroup, Workout


class WorkoutForm(forms.ModelForm):
    """Workout settings plus its ordered items, sent by the builder as JSON.

    ``items`` is ``[{"exercise": "<uuid>", "dur": 40}, ...]`` in play order.
    """

    items = forms.CharField(widget=forms.HiddenInput)

    class Meta:
        model = Workout
        fields = ["name", "description", "rest_seconds", "rounds", "round_rest_seconds"]
        widgets = {"description": forms.Textarea(attrs={"rows": 2})}

    def clean_items(self):
        try:
            raw = json.loads(self.cleaned_data["items"])
            wanted = [(uuid.UUID(str(i["exercise"])), int(i["dur"])) for i in raw]
        except (ValueError, TypeError, KeyError) as exc:
            raise forms.ValidationError("The exercise list could not be read.") from exc
        if not wanted:
            raise forms.ValidationError("Add at least one exercise.")
        if any(not 5 <= dur <= 3600 for _, dur in wanted):
            raise forms.ValidationError("Each exercise needs between 5 and 3600 seconds.")
        exercises = Exercise.objects.in_bulk([u for u, _ in wanted], field_name="uuid")
        missing = {u for u, _ in wanted} - set(exercises)
        if missing:
            raise forms.ValidationError("An exercise in the list no longer exists.")
        return [(exercises[u], dur) for u, dur in wanted]


class ExerciseForm(forms.ModelForm):
    types = forms.ModelMultipleChoiceField(
        queryset=ExerciseType.objects.all(),
        to_field_name="slug",
        widget=forms.CheckboxSelectMultiple,
        error_messages={"required": "Pick at least one type."},
    )
    muscles = forms.ModelMultipleChoiceField(
        queryset=MuscleGroup.objects.all(),
        to_field_name="name",
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )
    new_muscles = forms.CharField(
        required=False,
        label="Other muscles",
        help_text="Comma separated, for muscles not listed above.",
    )

    class Meta:
        model = Exercise
        fields = ["name", "types", "muscles", "one_sided", "default_duration", "description"]
        labels = {
            "one_sided": "Runs per side",
            "default_duration": "Default duration",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        clash = Exercise.objects.filter(name__iexact=name).exclude(pk=self.instance.pk)
        if clash.exists():
            raise forms.ValidationError("An exercise with this name already exists.")
        return name

    def clean_new_muscles(self):
        names = [n.strip() for n in self.cleaned_data["new_muscles"].split(",")]
        return [n[:1].upper() + n[1:] for n in names if n]

    def save(self, commit=True):
        exercise = super().save(commit=commit)
        if commit:
            extra = []
            for name in self.cleaned_data["new_muscles"]:
                muscle = MuscleGroup.objects.filter(name__iexact=name).first()
                extra.append(muscle or MuscleGroup.objects.create(name=name))
            exercise.muscles.add(*extra)
        return exercise
