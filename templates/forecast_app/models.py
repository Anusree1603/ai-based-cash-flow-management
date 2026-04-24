# Create your models here.

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal

class Category(models.Model):
    CATEGORY_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    
    name = models.CharField(max_length=100)
    category_type = models.CharField(max_length=10, choices=CATEGORY_TYPES)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Categories"
        unique_together = ['name', 'user']
    
    def __str__(self):
        return f"{self.name} ({self.category_type})"


class PaymentMode(models.Model):
    name = models.CharField(max_length=50)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    
    def __str__(self):
        return self.name


class Transaction(models.Model):
    TRANSACTION_TYPES = [
        ('income', 'Income'),
        ('expense', 'Expense'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    payment_mode = models.ForeignKey(PaymentMode, on_delete=models.SET_NULL, null=True)
    description = models.TextField(blank=True, null=True)
    date = models.DateField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} on {self.date}"


class Receivable(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    party_name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    description = models.TextField(blank=True, null=True)
    is_received = models.BooleanField(default=False)
    received_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Receivable from {self.party_name} - {self.amount}"


class Payable(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    party_name = models.CharField(max_length=200)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField()
    description = models.TextField(blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    paid_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payable to {self.party_name} - {self.amount}"


class CashFlowForecast(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    forecast_date = models.DateField()
    predicted_balance = models.DecimalField(max_digits=12, decimal_places=2)
    predicted_income = models.DecimalField(max_digits=12, decimal_places=2)
    predicted_expense = models.DecimalField(max_digits=12, decimal_places=2)
    confidence_score = models.FloatField(default=0.0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['forecast_date']
        unique_together = ['user', 'forecast_date']
    
    def __str__(self):
        return f"Forecast for {self.forecast_date} - Balance: {self.predicted_balance}"


class Alert(models.Model):
    ALERT_TYPES = [
        ('low_cash', 'Low Cash Warning'),
        ('high_spending', 'High Spending Alert'),
        ('payment_due', 'Payment Due'),
        ('trend', 'Spending Trend'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.alert_type} - {self.severity}"
    
# class Categorys(models.Model):
#     user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
#     category_name = models.CharField(max_length=500)
#     TYPE_CAT = [('INCOME','income'), ('EXPENSE','expense')]
#     category_type = models.CharField(max_length=100, choices=TYPE_CAT)

#     def __str__(self):
#         return self.category_name

    
# class Payments(models.Model):
#     payment_cat=models.CharField(max_length=500)
#     def __str__(self):
#         return self.payment_cat
    
    
# class Income(models.Model):
#     user=models.ForeignKey(User,max_length=100,on_delete=models.CASCADE)
#     amount=models.IntegerField()
#     date=models.DateField()
#     description=models.CharField(max_length=100)
#     payment_mode=models.ForeignKey(PaymentMode,on_delete=models.CASCADE,null=True)
#     category=models.ForeignKey(Category,on_delete=models.CASCADE,null=True)
#     def __str__(self):
#         return self.description

# class Expense(models.Model):
#     user=models.ForeignKey(User,max_length=100,on_delete=models.CASCADE)
#     amount=models.IntegerField()
#     date=models.DateField()
#     description=models.CharField(max_length=100)
#     payment_mode=models.ForeignKey(PaymentMode,on_delete=models.CASCADE,null=True)
#     category=models.ForeignKey(Category,on_delete=models.CASCADE,null=True)
#     def __str__(self):
#         return self.description
    
class Settings(models.Model):
    user=models.ForeignKey(User,max_length=100,on_delete=models.CASCADE)
    DURATION_CAT=[('MONTHLY','monthly'),('WEEKLY','weekly')]
    forecast_duration=models.CharField(max_length=100,choices=DURATION_CAT)
    alert_threshold_amount=models.DecimalField(decimal_places=5,max_digits=10)

    def __str__(self):
        return self.forecast_duration
    
class AlertSetting(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    income_alert_enabled = models.BooleanField(default=True)
    expense_alert_enabled = models.BooleanField(default=True)
    receivable_alert_enabled = models.BooleanField(default=True)
    payable_alert_enabled = models.BooleanField(default=True)