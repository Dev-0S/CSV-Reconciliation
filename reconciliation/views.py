import csv
import random
import io
import zipfile
from django.shortcuts import render
from django.http import HttpResponse
from django.contrib import messages

def index(request):
    """
    Reconciliator view: accepts two CSV files, performs reconciliation, and displays results.
    """
    reconciliation_result = None

    if request.method == 'POST':
        internal_file = request.FILES.get('internal_file')
        external_file = request.FILES.get('external_file')
        
        if not internal_file or not external_file:
            messages.error(request, "Both files are required.")
        else:
            try:
                # Dictionaries to store CSV rows keyed by trade_id
                internal_data = {}
                external_data = {}

                # Process the Internal CSV File
                internal_text = internal_file.read().decode('utf-8')
                internal_reader = csv.DictReader(io.StringIO(internal_text))
                for row in internal_reader:
                    trade_id = row.get('trade_id')
                    if trade_id:
                        internal_data[trade_id] = row

                # Process the External CSV File
                external_text = external_file.read().decode('utf-8')
                external_reader = csv.DictReader(io.StringIO(external_text))
                for row in external_reader:
                    trade_id = row.get('trade_id')
                    if trade_id:
                        external_data[trade_id] = row

                # Reconciliation
                reconciled = []           # Trades present in both files
                missing_in_external = []  # Trades in internal only
                missing_in_internal = []  # Trades in external only

                for trade_id, internal_trade in internal_data.items():
                    if trade_id in external_data:
                        external_trade = external_data[trade_id]
                        if internal_trade.get('amount') == external_trade.get('amount'):
                            status = 'Matched'
                        else:
                            status = 'Mismatch'
                        reconciled.append({
                            'trade_id': trade_id,
                            'internal_amount': internal_trade.get('amount'),
                            'external_amount': external_trade.get('amount'),
                            'status': status,
                        })
                    else:
                        missing_in_external.append(internal_trade)

                for trade_id, external_trade in external_data.items():
                    if trade_id not in internal_data:
                        missing_in_internal.append(external_trade)

                reconciliation_result = {
                    'reconciled': reconciled,
                    'missing_in_external': missing_in_external,
                    'missing_in_internal': missing_in_internal,
                }
            except Exception as e:
                messages.error(request, f"Error processing files: {str(e)}")

    return render(request, 'reconciliation/index.html', {'result': reconciliation_result})


def generate_csv_view(request):
    """
    CSV Generator view: Displays a form to name the CSV files.
    On form submission, generates 100 internal trades and matching external trades (with random errors),
    adds one extra trade in the external file, packages them into a ZIP, and returns the ZIP as a download.
    """
    if request.method == 'POST':
        # Get user-provided file names; add .csv if missing.
        internal_filename = request.POST.get('internal_filename', 'internal_trades.csv').strip()
        external_filename = request.POST.get('external_filename', 'external_trades.csv').strip()
        if not internal_filename.endswith('.csv'):
            internal_filename += '.csv'
        if not external_filename.endswith('.csv'):
            external_filename += '.csv'

        # Prepare CSV files in memory.
        internal_buffer = io.StringIO()
        external_buffer = io.StringIO()
        internal_writer = csv.writer(internal_buffer)
        external_writer = csv.writer(external_buffer)

        header = ["trade_id", "amount", "date"]
        internal_writer.writerow(header)
        external_writer.writerow(header)

        def format_date(i):
            day = ((i - 1) % 28) + 1
            return f"2025-01-{day:02d}"

        # Determine random number of errors between 2 and 9.
        total_errors = random.randint(2, 9)
        # One error is the extra trade that is in external but not internal.
        mismatches_count = total_errors - 1
        error_trade_ids = random.sample([f"T{i}" for i in range(1, 101)], mismatches_count)

        # Generate 100 trades.
        for i in range(1, 101):
            trade_id = f"T{i}"
            amount = 1000 + i * 10
            date = format_date(i)

            internal_writer.writerow([trade_id, amount, date])
            if trade_id in error_trade_ids:
                # Mismatch: add an error by increasing the amount by 50.
                external_amount = amount + 50
            else:
                external_amount = amount
            external_writer.writerow([trade_id, external_amount, date])

        # Add an extra trade in the external file.
        extra_trade_id = "T101"
        extra_amount = 1000 + 101 * 10
        extra_date = format_date(101)
        external_writer.writerow([extra_trade_id, extra_amount, extra_date])

        # Get CSV content.
        internal_csv_content = internal_buffer.getvalue()
        external_csv_content = external_buffer.getvalue()

        # Create a ZIP file in memory containing both CSV files.
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr(internal_filename, internal_csv_content)
            zip_file.writestr(external_filename, external_csv_content)
        zip_buffer.seek(0)

        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="generated_csv.zip"'
        return response

    else:
        # Render the CSV Generator form.
        return render(request, 'reconciliation/generate_csv.html')