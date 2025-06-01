# models.py
from django.db import models
from django.contrib.auth.models import User

class Team(models.Model):
    name = models.CharField(max_length=100)
    creator = models.ForeignKey(User, on_delete=models.CASCADE)
    team_id = models.AutoField(primary_key=True)
    is_active = models.BooleanField(default=False)  # Add this line

    def __str__(self):
        return self.name

class TeamPlayer(models.Model):
    STATUS_CHOICES = [
        ('ON_TEAM', 'On Team'),
        ('AVAILABLE', 'Available'),
        ('UNAVAILABLE', 'Unavailable'),
    ]
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='team_players')
    player_id = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='AVAILABLE',
    )
    
    class Meta:
        unique_together = ('team', 'player_id') # A player has a unique status per team

    def __str__(self):
        return f"Player {self.player_id} on {self.team.name} - {self.get_status_display()}"