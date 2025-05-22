# forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm

class MinimalUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        fields = ("username", "email")  # Include email if you want it

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].help_text = None  # Remove help text
        # self.fields['email'].help_text = None  # Remove email help text if you include email