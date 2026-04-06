from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from myApp.models import (
    Course,
    FeatureFlag,
    SystemSetting,
    Language,
    PlacementTest,
    PlacementQuestion,
    Voucher,
)
from myApp.services.feature_flags import is_feature_enabled, get_setting


class RolloutFoundationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="student", password="pass12345", email="student@test.local")
        self.staff = User.objects.create_user(username="admin", password="pass12345", is_staff=True, is_superuser=True)
        self.course = Course.objects.create(
            name="Test Course",
            slug="test-course",
            description="desc",
            short_description="short",
            is_paid=True,
            price=99,
            currency="USD",
        )

    def test_feature_flag_and_setting_helpers(self):
        FeatureFlag.objects.create(key="payments.paypal_enabled", is_enabled=True, rollout_percentage=100)
        SystemSetting.objects.create(key="site.title", value="Fluentory", value_type="string")
        self.assertTrue(is_feature_enabled("payments.paypal_enabled", self.user))
        self.assertEqual(get_setting("site.title"), "Fluentory")

    def test_public_pages_still_available(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        response = self.client.get(reverse("courses"))
        self.assertEqual(response.status_code, 200)

    def test_placement_test_api(self):
        test = PlacementTest.objects.create(name="Placement")
        q = PlacementQuestion.objects.create(
            test=test,
            question_text="What is 2 + 2?",
            question_type="mcq",
            options=["3", "4"],
            correct_answer="4",
            difficulty="A1",
            order=1,
        )
        self.client.login(username="student", password="pass12345")
        get_resp = self.client.get(reverse("placement_test_view"))
        self.assertEqual(get_resp.status_code, 200)
        post_resp = self.client.post(
            reverse("placement_test_view"),
            data={"answers": {str(q.id): "4"}},
            content_type="application/json",
        )
        self.assertEqual(post_resp.status_code, 200)
        self.assertTrue(post_resp.json().get("success"))

    def test_voucher_application(self):
        Voucher.objects.create(code="WELCOME10", discount_type="percent", discount_value=10, is_active=True)
        self.client.login(username="student", password="pass12345")
        response = self.client.post(reverse("apply_voucher", args=[self.course.slug]), {"code": "WELCOME10"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body.get("success"))
        self.assertIn("purchase_id", body)

    def test_staff_only_site_settings(self):
        self.client.login(username="admin", password="pass12345")
        response = self.client.post(
            reverse("dashboard_site_settings"),
            {"key": "email.rules.default_sender", "value": "team@fluentory.com", "value_type": "string"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SystemSetting.objects.filter(key="email.rules.default_sender").exists())

