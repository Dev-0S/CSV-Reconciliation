# CSV Reconciliation

A Django web application for reconciling CSV files containing trade records and generating sample CSV files with configurable errors.

## Overview

This project provides two main features:
- **Reconciliator:** Upload two CSV files (one with internal trade records and one with external records). The app compares them by trade ID, highlighting matched trades, mismatches (e.g., differences in amounts), and trades missing from one of the files.
- **CSV Generator:** Generate sample CSV files containing 100 trade records. The generator randomizes which records are mismatched (with a total error rate between 2 and 9 errors) and adds an extra trade to the external CSV.

## Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Dev-0S/CSV-Reconciliation.git
   cd CSV-Reconciliation
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install django
   python manage.py migrate
   python manage.py runserver
   
