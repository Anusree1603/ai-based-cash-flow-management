# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Transaction, Category, PaymentMode, Receivable, Payable, CashFlowForecast, Alert
from django.db.models import Sum, Q, Count
from django.db.models.functions import TruncMonth, TruncDate
from django.http import JsonResponse, HttpResponse
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
import json
import csv
from django.contrib.auth import authenticate, login
from .forms import RegisterForm,ReceivableForm,PayableForm,Settingsform
from .models import Settings
from .models import AlertSetting   
from django.db.models import Avg
from django.db.models.functions import TruncMonth
from .utils import calculate_current_balance, calculate_percentage_change, get_forecast_chart_data


def create_default_categories (user):

    """Create default income and expense categories for new user"""

    # Income categories

    income_categories = [

        'Salary', 'Freelance', 'Business Income', 'Investment Returns',
        'Rental Income', 'Bonus', 'Interest', 'Other Income'
    ]
    for cat_name in income_categories:
        Category.objects.get_or_create(
            name=cat_name,
            category_type='income',
            user=user
        )
    # Expense categories
    expense_categories = [
        'Entertainment', 'Rent', 'Groceries', 'Utilities', 'Transportation',
        'Healthcare', 'Education', 'Insurance', 'Shopping', 'Dining Out',
        'Travel', 'Savings', 'Investment', 'EMI', 'Mobile/Internet',
        'Clothing', 'Personal Care', 'Gifts', 'Subscriptions', 'Other Expenses'
    ]

    for cat_name in expense_categories:
        Category.objects.get_or_create(
            name=cat_name,
            category_type='expense',
            user=user
        )

def create_default_payment_modes (user):
    """Create default payment modes for new user"""

    payment_modes = [
        'Cash', 'Bank Transfer', 'UPI', 'Credit Card', 'Debit Card',
        'Cheque', 'Digital Wallet', 'Net Banking'
    ]

    for mode_name in payment_modes:
        PaymentMode.objects.get_or_create(
        name=mode_name,
        user=user

)

@login_required
def dashboard(request):
    today = timezone.now().date()
    first_day_month = today.replace(day=1)

    # ─────────────────────────────
    # Current balance (lifetime)
    # ─────────────────────────────
    current_balance = calculate_current_balance(request.user) or Decimal('0.00')

    # ─────────────────────────────
    # Current month income & expense
    # ─────────────────────────────
    monthly_income = (
        Transaction.objects.filter(
            user=request.user,
            transaction_type='income',
            date__gte=first_day_month
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0.00')
    )

    monthly_expense = (
        Transaction.objects.filter(
            user=request.user,
            transaction_type='expense',
            date__gte=first_day_month
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0.00')
    )

    monthly_net = monthly_income - monthly_expense

    # ─────────────────────────────
    # Previous month comparison
    # ─────────────────────────────
    prev_month_end = first_day_month - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)

    prev_month_income = (
        Transaction.objects.filter(
            user=request.user,
            transaction_type='income',
            date__range=(prev_month_start, prev_month_end)
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0.00')
    )

    prev_month_expense = (
        Transaction.objects.filter(
            user=request.user,
            transaction_type='expense',
            date__range=(prev_month_start, prev_month_end)
        ).aggregate(total=Sum('amount'))['total']
        or Decimal('0.00')
    )

    income_change = calculate_percentage_change(prev_month_income, monthly_income)
    expense_change = calculate_percentage_change(prev_month_expense, monthly_expense)

    # ─────────────────────────────
    # Forecast (30 days)
    # ─────────────────────────────
    forecast = CashFlowForecast.objects.filter(
        user=request.user,
        forecast_date__gte=today,
        forecast_date__lte=today + timedelta(days=30)
    ).first()

    # ─────────────────────────────
    # Recent activity & analytics
    # ─────────────────────────────
    recent_transactions = Transaction.objects.filter(
        user=request.user
    ).order_by('-date')[:10]

    alerts = Alert.objects.filter(
        user=request.user,
        is_read=False
    )[:5]

    spending_trends = (
        Transaction.objects.filter(
            user=request.user,
            transaction_type='expense',
            date__gte=first_day_month
        )
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')[:5]
    )

    forecast_data = get_forecast_chart_data(request.user)

    # ─────────────────────────────
    # Context (single source of truth)
    # ─────────────────────────────
    context = {
        'current_balance': current_balance,
        'monthly_income': monthly_income,
        'monthly_expense': monthly_expense,
        'monthly_net': monthly_net,
        'income_change': income_change,
        'expense_change': expense_change,
        'forecast': forecast,
        'recent_transactions': recent_transactions,
        'alerts': alerts,
        'spending_trends': spending_trends,
        'forecast_data': forecast_data,
    }

    return render(request, 'forecast_app/dashboard.html', context) 
def income_summary(request):
    today = timezone.now().date()
    last_year = today - timedelta(days=365)

    avg_monthly_income = (
        Transaction.objects.filter(
            user=request.user,
            transaction_type='income',
            date__gte=last_year
        )
        .values('date__year', 'date__month')
        .annotate(total=Sum('amount'))
        .aggregate(avg=Avg('total'))['avg']
        or 0
    )

    return render(
        request,
        'forecast_app/inc_summary.html',
        {'avg_monthly_income': avg_monthly_income}
    )


def expense_summary(request):
    today = timezone.now().date()
    last_year = today - timedelta(days=365)

    avg_monthly_expense = (
        Transaction.objects.filter(
            user=request.user,
            transaction_type='expense',
            date__gte=last_year
        )
        .values('date__year', 'date__month')
        .annotate(total=Sum('amount'))
        .aggregate(avg=Avg('total'))['avg']
        or 0
    )

    return render(
        request,
        'forecast_app/exp_summary.html',
        {'avg_monthly_expense': avg_monthly_expense}
    )

def avg_current_balance(request):
    user = request.user

    # Monthly income totals
    income_qs = (
        Transaction.objects
        .filter(user=user, transaction_type='income')
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
    )

    # Monthly expense totals
    expense_qs = (
        Transaction.objects
        .filter(user=user, transaction_type='expense')
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(total=Sum('amount'))
    )

    income_map = {row['month']: row['total'] for row in income_qs}
    expense_map = {row['month']: row['total'] for row in expense_qs}

    balances = []

    for month in income_map:
        income = income_map.get(month, 0)
        expense = expense_map.get(month, 0)
        balances.append(income - expense)

    avg_current_balance = (
        sum(balances) / len(balances) if balances else Decimal('0.00')
    )

    return render(
        request,
        'forecast_app/avg_balance.html',
        {'avg_current_balance': avg_current_balance}
    )

def income_list(request):
    incomes = Transaction.objects.filter(
        user=request.user,
        transaction_type='income'
    ).select_related('category', 'payment_mode') \
     .order_by('-date')
    
    total_income = incomes.aggregate(total=Sum('amount'))['total'] or 0

    LOW_INCOME_LIMIT = 5000000
    total_income_alert = total_income < LOW_INCOME_LIMIT

    context = {
        'incomes': incomes,
        'total_income': total_income,
        'total_income_alert': total_income_alert,
        'low_income_limit': LOW_INCOME_LIMIT,
    }

    return render(request, 'forecast_app/income_list.html', context)

# @login_required
from decimal import Decimal
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone

def add_income(request):
    if request.method == 'POST':
        amounts = request.POST.getlist('amount[]')
        categories = request.POST.getlist('category[]')
        payment_modes = request.POST.getlist('payment_mode[]')
        dates = request.POST.getlist('date[]')
        descriptions = request.POST.getlist('description[]')

        transactions = []

        try:
            for i in range(len(amounts)):
                if not amounts[i]:
                    continue

                transactions.append(
                    Transaction(
                        user=request.user,
                        transaction_type='income',
                        amount=Decimal(amounts[i]),
                        category_id=categories[i],
                        payment_mode_id=payment_modes[i],
                        description=descriptions[i],
                        date=dates[i]
                    )
                )

            Transaction.objects.bulk_create(transactions)

            messages.success(
                request,
                f"{len(transactions)} income records added successfully."
            )

            generate_forecasts(request.user)

            return redirect('income_list')

        except Exception as e:
            messages.error(request, str(e))

    categories = Category.objects.filter(
        user=request.user,
        category_type='income'
    )
    payment_modes = PaymentMode.objects.filter(user=request.user)

    return render(request, 'forecast_app/add_income.html', {
        'categories': categories,
        'payment_modes': payment_modes
    })

def edit_income(request, pk):
    income = Transaction.objects.get(pk=pk, user=request.user)

    if request.method == 'POST':
        income.amount = request.POST.get('amount')
        income.category_id = request.POST.get('category')
        income.payment_mode_id = request.POST.get('payment_mode')
        income.description = request.POST.get('description')
        income.date = request.POST.get('date')
        income.save()

        messages.success(request, 'Income updated successfully')
        return redirect('income_list')

    categories = Category.objects.filter(user=request.user, category_type='income')
    payment_modes = PaymentMode.objects.filter(user=request.user)

    return render(request, 'forecast_app/edit_income.html', {
        'income': income,
        'categories': categories,
        'payment_modes': payment_modes
    })

def delete_income(request, pk):
    income = Transaction.objects.get(pk=pk, user=request.user)
    income.delete()
    messages.success(request, 'Income deleted successfully')
    return redirect('income_list')


from django.contrib.auth.decorators import login_required
from .models import Transaction

@login_required
def expense_list(request):
    expenses = Transaction.objects.filter(
        user=request.user,
        transaction_type='expense'
    ).select_related('category', 'payment_mode') \
     .order_by('-date')
    total_expense = expenses.aggregate(total=Sum('amount'))['total'] or 0

    HIGH_EXPENSE_LIMIT = 300000
    total_expense_alert = total_expense > HIGH_EXPENSE_LIMIT

    return render(request, 'forecast_app/expense_list.html', {
        'expenses': expenses,
        'total_expense': total_expense,
        'total_expense_alert': total_expense_alert,
        'high_expense_limit': HIGH_EXPENSE_LIMIT,
    })


# @login_required
from decimal import Decimal
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone

def add_expense(request):
    if request.method == 'POST':
        amounts = request.POST.getlist('amount[]')
        categories = request.POST.getlist('category[]')
        payment_modes = request.POST.getlist('payment_mode[]')
        dates = request.POST.getlist('date[]')
        descriptions = request.POST.getlist('description[]')

        transactions = []

        try:
            for i in range(len(amounts)):
                if not amounts[i]:
                    continue

                transactions.append(
                    Transaction(
                        user=request.user,
                        transaction_type='expense',
                        amount=Decimal(amounts[i]),
                        category_id=categories[i],
                        payment_mode_id=payment_modes[i],
                        description=descriptions[i],
                        date=dates[i] or timezone.now().date()
                    )
                )

            Transaction.objects.bulk_create(transactions)

            check_low_cash_alert(request.user)
            generate_forecasts(request.user)

            messages.success(
                request,
                f"{len(transactions)} expense records added successfully."
            )

            return redirect('expense_list')

        except Exception as e:
            messages.error(request, f"Error adding expense: {e}")

    categories = Category.objects.filter(
        user=request.user,
        category_type='expense'
    )
    payment_modes = PaymentMode.objects.filter(user=request.user)

    return render(request, 'forecast_app/add_expense.html', {
        'categories': categories,
        'payment_modes': payment_modes,
    })

def edit_expense(request, pk):
    expense = Transaction.objects.get(
        pk=pk,
        user=request.user,
        transaction_type='expense'
    )

    if request.method == 'POST':
        expense.amount = request.POST.get('amount')
        expense.category_id = request.POST.get('category')
        expense.payment_mode_id = request.POST.get('payment_mode')
        expense.description = request.POST.get('description')
        expense.date = request.POST.get('date')
        expense.save()

        messages.success(request, 'Expense updated successfully')
        return redirect('expense_list')

    categories = Category.objects.filter(user=request.user, category_type='expense')
    payment_modes = PaymentMode.objects.filter(user=request.user)

    return render(request, 'forecast_app/edit_expense.html', {
        'expense': expense,
        'categories': categories,
        'payment_modes': payment_modes
    })

def delete_expense(request, pk):
    expense = Transaction.objects.get(
        pk=pk,
        user=request.user,
        transaction_type='expense'
    )
    expense.delete()
    messages.success(request, 'Expense deleted successfully')
    return redirect('expense_list')


# @login_required
def receivables_payables(request):
    receivables = Receivable.objects.filter(user=request.user)
    payables = Payable.objects.filter(user=request.user)
    
    context = {
        'receivables': receivables,
        'payables': payables,
    }
    
    return render(request, 'forecast_app/receivables_payables.html', context)


# @login_required
def forecast_analytics(request):
    forecasts = CashFlowForecast.objects.filter(user=request.user)[:180]  # 6 months
    
    context = {
        'forecasts': forecasts,
    }
    
    return render(request, 'forecast_app/forecast_analytics.html', context)


# # @login_required
# def alerts_view(request):
#     all_alerts = Alert.objects.filter(user=request.user)
    
#     context = {
#         'alerts': all_alerts,
#     }
    
#     return render(request, 'forecast_app/alerts.html', context)


# @login_required
def export_data(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="cashflow_data.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Date', 'Type', 'Category', 'Amount', 'Payment Mode', 'Description'])
    
    transactions = Transaction.objects.filter(user=request.user)
    for txn in transactions:
        writer.writerow([
            txn.date,
            txn.transaction_type,
            txn.category.name if txn.category else '',
            txn.amount,
            txn.payment_mode.name if txn.payment_mode else '',
            txn.description
        ])
    
    return response




def calculate_current_balance(user):
    total_income = Transaction.objects.filter(
        user=user,
        transaction_type='income'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    total_expense = Transaction.objects.filter(
        user=user,
        transaction_type='expense'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    
    return total_income - total_expense


def calculate_percentage_change(old_value, new_value):
    if old_value == 0:
        return 100 if new_value > 0 else 0
    return round(((new_value - old_value) / old_value) * 100, 1)


def generate_forecasts(user):
    """AI-based cash flow forecasting"""
    from datetime import timedelta
    
    today = timezone.now().date()
    
    # Get historical data (last 90 days)
    ninety_days_ago = today - timedelta(days=90)
    
    avg_daily_income = Transaction.objects.filter(
        user=user,
        transaction_type='income',
        date__gte=ninety_days_ago
    ).aggregate(avg=Sum('amount'))['avg'] or Decimal('0.00')
    avg_daily_income = avg_daily_income / 90
    
    avg_daily_expense = Transaction.objects.filter(
        user=user,
        transaction_type='expense',
        date__gte=ninety_days_ago
    ).aggregate(avg=Sum('amount'))['avg'] or Decimal('0.00')
    avg_daily_expense = avg_daily_expense / 90
    
    current_balance = calculate_current_balance(user)
    
    # Generate forecasts for next 180 days
    for i in range(1, 181):
        forecast_date = today + timedelta(days=i)
        predicted_income = avg_daily_income * i
        predicted_expense = avg_daily_expense * i
        predicted_balance = current_balance + predicted_income - predicted_expense
        
        CashFlowForecast.objects.update_or_create(
            user=user,
            forecast_date=forecast_date,
            defaults={
                'predicted_balance': predicted_balance,
                'predicted_income': predicted_income,
                'predicted_expense': predicted_expense,
                'confidence_score': 0.75
            }
        )


def check_low_cash_alert(user):
    """Check if cash balance is low and create alert"""
    current_balance = calculate_current_balance(user)
    
    if current_balance < 50000:  # Threshold: ₹50,000
        Alert.objects.create(
            user=user,
            alert_type='low_cash',
            severity='high',
            message=f'Your current balance (₹{current_balance}) is below ₹50,000 threshold.'
        )


def get_forecast_chart_data(user):
    """Get forecast data for next 6 months"""
    today = timezone.now().date()
    forecast_data = []
    
    for month in range(1, 7):
        forecast_date = today + timedelta(days=30 * month)
        forecast = CashFlowForecast.objects.filter(
            user=user,
            forecast_date__lte=forecast_date
        ).order_by('-forecast_date').first()
        
        if forecast:
            forecast_data.append(float(forecast.predicted_balance))
        else:
            forecast_data.append(0)
    
    return forecast_data

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("dashboard")  # change if your dashboard URL name is different
        else:
            messages.error(request, "Invalid username or password")

    return render(request, "forecast_app/login.html")


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user=form.save()
            create_default_categories (user)
            create_default_payment_modes(user)
            login(request,user)
            messages.success(request, "Account created successfully. Please login.")
            return redirect("login")
    else:
        form = RegisterForm()

    return render(request, "forecast_app/register.html", {"form": form})

# def cattable(request):
#     catts = Categorys.objects.all()
#     return render(request, 'cattable.html', {'catts': catts})

# def catform(request):
#     if request.method == "POST":
#         Categorys.objects.create(
#             category_name=request.POST.get('category_name'),
#             category_type=request.POST.get('category_type'),
#         )
#         return redirect("cattable")
#     return render(request,'catform.html')

# def catupdate(request,id):
#     cattr=get_object_or_404(Categorys,id=id)
#     if request.method=="POST":
#             cattr.category_name=request.POST.get('category_name')
#             cattr.category_type=request.POST.get('category_type')
#             cattr.save()
#             return redirect("cattable")
#     return render(request,'catupdate.html',{'cattr':cattr})

# def catdelete(request,id):
#     cattr=get_object_or_404(Categorys,id=id)
#     cattr.delete()
#     return redirect("cattable")

# def Category_form(request):
#     if request.method == "POST":
#         form = Categorysform(request.POST)
#         if form.is_valid():
#             category = form.save(commit=False)
#             category.user = request.user
#             category.save()
#             if category.category_type == "INCOME":
#                 return redirect("incpy")
        
#             else:
#                 return redirect("exppy")
#     else:
#         form = Categorysform()   

#     return render(request, "catform.html", {"form": form})

# def inctable(request):
#     incs = Income.objects.all()

#     total_income = incs.aggregate(total=Sum('amount'))['total'] or 0

#     LOW_INCOME_LIMIT = 5000000
#     total_income_alert = total_income < LOW_INCOME_LIMIT

#     context = {
#         'incs': incs,
#         'total_income': total_income,
#         'total_income_alert': total_income_alert,
#         'low_income_limit': LOW_INCOME_LIMIT,
#     }
#     return render(request, 'forecast_app/inctable.html', context)


# def incform(request):
#     if request.method == "POST":
#         Income.objects.create(
#             amount=request.POST.get('amount'),
#             date=request.POST.get('date'),
#             category=request.POST.get('category'),
#             payment_mode=request.POST.get('payment_mode'),
#             description=request.POST.get('description'),
#         )
#         return redirect("inctable")
#     return render(request,'forecast_app/incform.html')

# def incupdate(request,id):
#     incer=get_object_or_404(Income,id=id)
#     if request.method=="POST":
#             incer.amount=request.POST.get('amount')
#             incer.date=request.POST.get('date')
#             incer.description=request.POST.get('description')
#             cat_name = request.POST.get('category')
#             if cat_name:
#                 incer.category = get_object_or_404(Category, income_cat=cat_name)
#             pay_name = request.POST.get('payment_mode')
#             if pay_name:
#                 incer.payment_mode = get_object_or_404(Payments, payment_cat=pay_name)
#                 incer.save()
#             return redirect("inctable")
#     return render(request,'forecast_app/incupdate.html',{'incer':incer})

# def incdelete(request,id):
#     incer=get_object_or_404(Income,id=id)
#     incer.delete()
#     return redirect("inctable")

# def Income_form(request):
#     if request.method == "POST":
#         form = Incomeform(request.POST)
#         if form.is_valid():
#             income = form.save(commit=False)  
#             income.user = request.user        
#             income.save()
#             return redirect("inctable")
#     else:
#         form = Incomeform()
#     return render(request, 'forecast_app/incform.html', {'form': form})

# def extable(request):
#     expns = Expense.objects.all()
#     total_expense = expns.aggregate(total=Sum('amount'))['total'] or 0

#     HIGH_EXPENSE_LIMIT = 1000000
#     total_expense_alert = total_expense > HIGH_EXPENSE_LIMIT

#     context = {
#         'expns': expns,
#         'total_expense': total_expense,
#         'total_expense_alert': total_expense_alert,
#         'high_expense_limit': HIGH_EXPENSE_LIMIT,
#     }
#     return render(request, 'forecast_app/extable.html', context)


# def exform(request):
#     if request.method == "POST":
#         Expense.objects.create(
#             amount=request.POST.get('amount'),
#             date=request.POST.get('date'),
#             category=request.POST.get('category'),
#             payment_mode=request.POST.get('payment_mode'),
#             description=request.POST.get('description'),
#         )
#         return redirect("extable")
#     return render(request,'forecast_app/exform.html')

# def expupdate(request,id):
#     expr=get_object_or_404(Expense,id=id)
#     if request.method=="POST":
#             expr.amount=request.POST.get('amount')
#             expr.date=request.POST.get('date')
#             expr.description=request.POST.get('description')
#             catt_name = request.POST.get('category')
#             if catt_name:
#                 expr.category = get_object_or_404(Category, expense_cat=catt_name)
#             pay_name = request.POST.get('payment_mode')
#             if pay_name:
#                 expr.payment_mode = get_object_or_404(Payments, payment_cat=pay_name)
#                 expr.save()
#             return redirect("extable")
#     return render(request,'forecast_app/exupdate.html',{'expr':expr})

# def expdelete(request,id):
#     expr=get_object_or_404(Expense,id=id)
#     expr.delete()
#     return redirect("extable")

# def Expense_form(request):
#     if request.method == "POST":
#         form = Expenseform(request.POST)
#         if form.is_valid():
#             expense = form.save(commit=False)  
#             expense.user = request.user        
#             expense.save()
#             return redirect("extable")
#     else:
#         form = Expenseform()
#     return render(request, 'forecast_app/exform.html', {'form': form})

@login_required
def Rectable(request):
    recs = Receivable.objects.filter(user=request.user).order_by('-id')

    # -------------------
    # FILTERS
    # -------------------
    party = request.GET.get("party", "")
    due_date = request.GET.get("due_date", "")

    if party:
        recs = recs.filter(party_name__istartswith=party)

    if due_date:
        recs = recs.filter(due_date=due_date)

    recs = recs.order_by("-id")

    pending_recs = recs.filter(is_received=False)

    party_list = (
        Receivable.objects
        .filter(user=request.user)
        .values_list("party_name", flat=True)
        .distinct()
        .order_by("party_name")
    )

    return render(request, "forecast_app/rectable.html", {
        "recs": recs,
        "pending_recs": pending_recs,
        "pending_count": pending_recs.count(),
        "party": party,
        "due_date": due_date,
        "party_list": party_list,
    })

from decimal import Decimal
from django.shortcuts import render, redirect
from django.utils import timezone
from django.contrib import messages
from .models import Receivable


def Recform(request):
    if request.method == "POST":
        party_names = request.POST.getlist("party_name[]")
        amounts = request.POST.getlist("amount[]")
        due_dates = request.POST.getlist("due_date[]")
        descriptions = request.POST.getlist("description[]")
        received_dates = request.POST.getlist("received_date[]")

        receivables = []

        try:
            for i in range(len(party_names)):
                if not party_names[i] or not amounts[i]:
                    continue

                # checkbox logic
                is_received = False
                received_date = None

                if i < len(received_dates) and received_dates[i]:
                    is_received = True
                    received_date = received_dates[i]

                receivables.append(
                    Receivable(
                        user=request.user,
                        party_name=party_names[i],
                        amount=Decimal(amounts[i]),
                        due_date=due_dates[i],
                        description=descriptions[i],
                        is_received=is_received,
                        received_date=received_date,
                    )
                )

            Receivable.objects.bulk_create(receivables)

            messages.success(
                request,
                f"{len(receivables)} receivable records added successfully."
            )

            return redirect("rectable")

        except Exception as e:
            messages.error(request, str(e))

    return render(request, "forecast_app/recform.html")

def Recupdate(request, id):
    recer = get_object_or_404(Receivable, id=id)

    if request.method == "POST":
        recer.party_name = request.POST.get('party_name')
        recer.amount = request.POST.get('amount')
        recer.due_date = request.POST.get('due_date')
        recer.description = request.POST.get('description')

        is_received = request.POST.get('is_received') == 'on'
        recer.is_received = is_received

        if is_received:
            recer.received_date = timezone.now().date()
        else:
            recer.received_date = None   # ✅ KEY LINE

        recer.save()
        return redirect("rectable")

    return render(request, 'forecast_app/recupdate.html', {'recer': recer})
def Recdelete(request,id):
    recer=get_object_or_404(Receivable,id=id)
    recer.delete()
    return redirect("rectable")

def Recievable_form(request):
    if request.method == "POST":
        form = ReceivableForm(request.POST)
        if form.is_valid():
            recieved = form.save(commit=False)  
            recieved.user = request.user        
            recieved.save()
            return redirect("rectable")
    else:
        form = ReceivableForm()
    return render(request, 'forecast_app/recform.html', {'form': form})

@login_required
def Paytable(request):
    pays = Payable.objects.filter(user=request.user).order_by('-id')

    party = request.GET.get("party", "")
    due_date = request.GET.get("due_date", "")

    if party:
        pays = pays.filter(party_name__istartswith=party)

    if due_date:
        pays = pays.filter(due_date=due_date)

    pays = pays.order_by("-id")
    pending_pays = pays.filter(is_paid=False)

    party_list = (
        Payable.objects
        .filter(user=request.user)
        .values_list("party_name", flat=True)
        .distinct()
        .order_by("party_name")
    )

    return render(request, "forecast_app/paytable.html", {
        "pays": pays,
        "pending_pays": pending_pays,
        "pending_count": pending_pays.count(),
        "party": party,
        "due_date": due_date,
        "party_list": party_list,
    })

from decimal import Decimal
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import Payable


def Payform(request):
    if request.method == "POST":
        party_names = request.POST.getlist("party_name[]")
        amounts = request.POST.getlist("amount[]")
        due_dates = request.POST.getlist("due_date[]")
        descriptions = request.POST.getlist("description[]")
        paid_dates = request.POST.getlist("paid_date[]")

        payables = []

        for i in range(len(party_names)):
            if not party_names[i] or not amounts[i]:
                continue

            is_paid = False
            paid_date = None

            if i < len(paid_dates) and paid_dates[i]:
                is_paid = True
                paid_date = paid_dates[i]

            payables.append(
                Payable(
                    user=request.user,
                    party_name=party_names[i],
                    amount=Decimal(amounts[i]),
                    due_date=due_dates[i],
                    description=descriptions[i],
                    is_paid=is_paid,
                    paid_date=paid_date
                )
            )

        Payable.objects.bulk_create(payables)

        messages.success(
            request,
            f"{len(payables)} payable records added successfully."
        )

        return redirect("paytable")

    return render(request, "forecast_app/payform.html")



def Payupdate(request,id):
    payer=get_object_or_404(Payable,id=id)
    if request.method=="POST":
            payer.party_name=request.POST.get('party_name')
            payer.amount=request.POST.get('amount')
            payer.due_date=request.POST.get('due_date')
            payer.description=request.POST.get('description')
            is_paid = request.POST.get('is_paid') == 'on'
            payer.is_paid = is_paid

            if is_paid:
                payer.paid_date = timezone.now().date()
            else:
                payer.paid_date = None   # ✅ KEY LINE
            payer.save()   
            return redirect("paytable")
    return render(request,'forecast_app/payupdate.html',{'payer':payer})

def Paydelete(request,id):
    payer=get_object_or_404(Payable,id=id)
    payer.delete()
    return redirect("paytable")

def Payable_form(request):
    if request.method == "POST":
        form = PayableForm(request.POST)
        if form.is_valid():
            paid = form.save(commit=False)  
            paid.user = request.user        
            paid.save()
            return redirect("paytable")
    else:
        form = PayableForm()
    return render(request, 'forecast_app/payform.html', {'form': form})

def rp_home(request):
    return render(request, 'forecast_app/rec_pay.html')          

@login_required
def Settable(request):
    sets = Settings.objects.filter(user=request.user)
    return render(request, 'forecast_app/settable.html', {'sets': sets})

def Setform(request):
    if request.method == "POST":
        Settings.objects.create(
            forecast_duration=request.POST.get('forecast_duration'),
            alert_threshold_amount=request.POST.get('alert_threshold_amount'),
        )
        return redirect("settable")
    return render(request,'forecast_app/setform.html')

def Setupdate(request, id):
    setter = get_object_or_404(Settings, id=id)

    if request.method == "POST":
        form = Settingsform(request.POST, instance=setter)
        if form.is_valid():
            form.save()
            return redirect("settable")
    else:
        form = Settingsform(instance=setter)

    return render(request, 'forecast_app/setupdate.html', {
        'form': form
    })


def Setdelete(request,id):
    setter=get_object_or_404(Settings,id=id)
    setter.delete()
    return redirect("settable")

def Settings_form(request):
    if request.method == "POST":
        form = Settingsform(request.POST)
        if form.is_valid():
            sett = form.save(commit=False)  
            sett.user = request.user        
            sett.save()
            return redirect("settable")
    else:
        form = Settingsform()
    return render(request, 'forecast_app/setform.html', {'form': form})   

def alerts(request):

    setting, _ = AlertSetting.objects.get_or_create(user=request.user)

    
    # ===== INCOME ALERT =====
    total_income = Transaction.objects.filter(
        user=request.user,
        transaction_type='income'
    ).aggregate(total=Sum('amount'))['total'] or 0

    income_limit = 5000000
    income_alert = total_income < income_limit and setting.income_alert_enabled

    # ===== EXPENSE ALERT =====
    total_expense = Transaction.objects.filter(
        user=request.user,
        transaction_type='expense'
    ).aggregate(total=Sum('amount'))['total'] or 0

    expense_limit = 3000000
    expense_alert = total_expense > expense_limit and setting.expense_alert_enabled

    # ===== RECEIVABLES =====
    pending_receivables = Receivable.objects.filter(is_received=False) \
        if setting.receivable_alert_enabled else []

    # ===== PAYABLES =====
    pending_payables = Payable.objects.filter(is_paid=False) \
        if setting.payable_alert_enabled else []

    context = {
        'setting': setting,

        'total_income': total_income,
        'income_limit': income_limit,
        'income_alert': income_alert,

        'total_expense': total_expense,
        'expense_limit': expense_limit,
        'expense_alert': expense_alert,

        'pending_receivables': pending_receivables,
        'pending_payables': pending_payables,
    }

    return render(request, 'forecast_app/al_nt.html', context)


def toggle_single_alert(request, alert_type):
    setting, _ = AlertSetting.objects.get_or_create(user=request.user)

    if alert_type == "income":
        setting.income_alert_enabled = not setting.income_alert_enabled
    elif alert_type == "expense":
        setting.expense_alert_enabled = not setting.expense_alert_enabled
    elif alert_type == "receivable":
        setting.receivable_alert_enabled = not setting.receivable_alert_enabled
    elif alert_type == "payable":
        setting.payable_alert_enabled = not setting.payable_alert_enabled

    setting.save()
    return redirect('alerts')
