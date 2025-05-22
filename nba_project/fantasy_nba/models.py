# models.py
from django.db import models
from django.contrib.auth.models import User

class Team(models.Model):
    name = models.CharField(max_length=100)
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    team_id = models.AutoField(primary_key=True)

class TeamPlayer(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')
    player_id = models.IntegerField()
    player_name = models.CharField(max_length=100)
    is_available = models.BooleanField(default=True)