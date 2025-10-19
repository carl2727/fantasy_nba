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

class DraftPick(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='draft_picks')
    player_id = models.CharField(max_length=20)
    pick_number = models.IntegerField()

    class Meta:
        # A player can only have one pick number per team,
        # and a pick number can only be assigned to one player per team.
        unique_together = (('team', 'player_id'), ('team', 'pick_number'))
        ordering = ['pick_number']

    def __str__(self):
        return f"Team: {self.team.name} - Pick {self.pick_number}: Player {self.player_id}"