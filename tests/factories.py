"""FactoryBoy factories for every model. Always call them with ``.create()``."""

from datetime import timedelta

import factory
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounts.models import Passkey, SignInRequest
from apps.activity.models import ActivitySession, DiscardedSession, SessionEntry
from apps.library.models import Exercise, ExerciseType, MuscleGroup, Workout, WorkoutItem


class UserFactory(factory.django.DjangoModelFactory):
    """An account as sign-in makes one: the email is the username, no password."""

    class Meta:
        """Factory metadata."""

        model = get_user_model()
        django_get_or_create = ("username",)

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    username = factory.SelfAttribute("email")
    password = factory.django.Password(None)


class SignInRequestFactory(factory.django.DjangoModelFactory):
    """A live sign-in request. Use ``apps.accounts.sign_in.issue`` to get its token and code."""

    class Meta:
        """Factory metadata."""

        model = SignInRequest

    email = factory.Sequence(lambda n: f"signin{n}@example.com")
    token_hash = factory.Sequence(lambda n: f"{n:064x}")
    code_hash = "0" * 64
    expires_at = factory.LazyFunction(lambda: timezone.now() + timedelta(minutes=15))


class PasskeyFactory(factory.django.DjangoModelFactory):
    """A saved passkey (its key is a placeholder: it can't verify a real ceremony)."""

    class Meta:
        """Factory metadata."""

        model = Passkey

    user = factory.SubFactory(UserFactory)
    credential_id = factory.Sequence(lambda n: f"credential-{n}")
    public_key = b"not-a-real-key"
    name = "Passkey on iPhone"


def exercise_type(slug: str) -> ExerciseType:
    """Return one of the five types the data migration made (aerobic, strength, ...)."""
    return ExerciseType.objects.get(slug=slug)


class MuscleGroupFactory(factory.django.DjangoModelFactory):
    """A shared muscle group. Pass ``owner=`` for one only that account sees."""

    class Meta:
        """Factory metadata."""

        model = MuscleGroup

    owner = None
    name = factory.Sequence(lambda n: f"Muscle {n}")


class ExerciseFactory(factory.django.DjangoModelFactory):
    """An exercise in a new account's library, typed as strength unless ``types=`` says."""

    class Meta:
        """Factory metadata."""

        model = Exercise
        skip_postgeneration_save = True

    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Exercise {n}")

    @factory.post_generation
    def types(self, create: bool, extracted: list[ExerciseType] | None) -> None:
        """Add ``types=[...]``, or strength."""
        if create:
            self.types.set(extracted if extracted is not None else [exercise_type("strength")])

    @factory.post_generation
    def muscles(self, create: bool, extracted: list[MuscleGroup] | None) -> None:
        """Add ``muscles=[...]`` when given."""
        if create and extracted:
            self.muscles.set(extracted)


class WorkoutFactory(factory.django.DjangoModelFactory):
    """An empty workout. Add items with WorkoutItemFactory."""

    class Meta:
        """Factory metadata."""

        model = Workout

    owner = factory.SubFactory(UserFactory)
    name = factory.Sequence(lambda n: f"Workout {n}")


class WorkoutItemFactory(factory.django.DjangoModelFactory):
    """One exercise in a workout, both belonging to the same account."""

    class Meta:
        """Factory metadata."""

        model = WorkoutItem

    workout = factory.SubFactory(WorkoutFactory)
    exercise = factory.SubFactory(ExerciseFactory, owner=factory.SelfAttribute("..workout.owner"))
    order = 0
    duration_seconds = 40


class ActivitySessionFactory(factory.django.DjangoModelFactory):
    """A completed two-minute session, logged with no workout attached."""

    class Meta:
        """Factory metadata."""

        model = ActivitySession

    owner = factory.SubFactory(UserFactory)
    workout_name = "Legs"
    started_at = factory.LazyFunction(lambda: timezone.now() - timedelta(minutes=2))
    ended_at = factory.LazyFunction(timezone.now)
    completed = True
    seconds_worked = 80


class SessionEntryFactory(factory.django.DjangoModelFactory):
    """Time worked on one exercise in a session."""

    class Meta:
        """Factory metadata."""

        model = SessionEntry

    session = factory.SubFactory(ActivitySessionFactory)
    exercise = None
    exercise_name = "Split squat"
    seconds_worked = 80


class DiscardedSessionFactory(factory.django.DjangoModelFactory):
    """A session thrown away on the finish screen."""

    class Meta:
        """Factory metadata."""

        model = DiscardedSession

    owner = factory.SubFactory(UserFactory)
