import os, json, smtplib, ssl, urllib.parse, urllib.request, datetime as dt, calendar, argparse
from email.message import EmailMessage

TODAY = dt.date.today()


def post(url, data, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {}, method='POST')
    with urllib.request.urlopen(req, timeout=35) as response:
        return response.read()


def subtract_months(day, months):
    total = day.year * 12 + day.month - 1 - months
    year, month = divmod(total, 12)
    month += 1
    return dt.date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def reminder_label(due, today=None):
    today = today or TODAY
    if today == subtract_months(due, 3): return '3 måneder før'
    if today == subtract_months(due, 1): return '1 måned før'
    if today == due - dt.timedelta(days=10): return '10 dage før'
    if today == due + dt.timedelta(days=1): return 'Udløbet i går'
    return None


def test_dates():
    """Test dato-reglerne lokalt uden Dropbox eller e-mail."""
    today = TODAY
    cases = [
        ('3 måneder før', today.replace(year=today.year + (today.month + 2) // 12, month=(today.month + 2) % 12 + 1)),
        ('1 måned før', today.replace(year=today.year + today.month // 12, month=today.month % 12 + 1)),
        ('10 dage før', today + dt.timedelta(days=10)),
        ('Udløbet i går', today - dt.timedelta(days=1)),
    ]
    for expected, due in cases:
        actual = reminder_label(due, today)
        print(f'{expected}: frist {due.isoformat()} -> {actual}')
        if actual != expected:
            raise AssertionError(f'Forventet {expected!r}, fik {actual!r}')
    assert reminder_label(today + dt.timedelta(days=40), today) is None
    # Kontroller månedsskift inkl. 31. dato og skudår.
    assert subtract_months(dt.date(2028, 5, 31), 3) == dt.date(2028, 2, 29)
    assert subtract_months(dt.date(2027, 5, 31), 3) == dt.date(2027, 2, 28)
    print('ALLE DATOTESTS BESTÅET. Ingen Dropbox-data læst eller ændret. Ingen e-mails sendt.')


def main():
    app_key = os.environ['DROPBOX_APP_KEY']
    refresh = os.environ['DROPBOX_REFRESH_TOKEN']
    gmail_user = os.environ['GMAIL_USER']
    gmail_password = os.environ['GMAIL_APP_PASSWORD'].replace(' ', '').replace('\u00a0', '')
    token = json.loads(post('https://api.dropboxapi.com/oauth2/token', urllib.parse.urlencode({
        'grant_type': 'refresh_token', 'refresh_token': refresh, 'client_id': app_key
    }).encode(), {'Content-Type': 'application/x-www-form-urlencoded'}))['access_token']
    raw = post('https://content.dropboxapi.com/2/files/download', b'', {
        'Authorization': 'Bearer ' + token, 'Dropbox-API-Arg': json.dumps({'path': '/familie-data.json'})
    })
    records = json.loads(raw)['records']
    recipients = {
        '8151213@gmail.com': {'Carsten', 'Sofie', 'Erik', 'Emil'},
        'asskriver@gmail.com': {'Sofie', 'Erik', 'Emil'},
    }
    for recipient, persons in recipients.items():
        matches = []
        for r in records:
            if r.get('person') not in persons or not r.get('due'): continue
            try: due = dt.date.fromisoformat(r['due'])
            except (ValueError, TypeError): continue
            label = reminder_label(due)
            if not label: continue
            kind = r.get('type', '')
            certainty = r.get('certainty', 'confirmed')
            qualifier = (' (vejledende dato)' if certainty == 'estimated' else
                         ' (kræver faglig vurdering)' if certainty == 'review' else '')
            matches.append(f"• {r['person']}: {kind} – {r.get('name', 'Registrering')}{qualifier}\n  Dato: {due.strftime('%d.%m.%Y')} · {label}")
        if not matches: continue
        msg = EmailMessage()
        msg['From'] = gmail_user
        msg['To'] = recipient
        msg['Subject'] = f'Familie rejseoverblik – {len(matches)} påmindelse(r)'
        msg.set_content('Automatiske påmindelser fra Familie rejseoverblik:\n\n' + '\n\n'.join(matches) + '\n\nÅbn https://sgcholm.github.io/familie-rejseoverblik/ for detaljer.\n\nBemærk: Vaccinationsfrister er ikke nødvendigvis medicinske udløbsdatoer.')
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=ssl.create_default_context(), timeout=35) as smtp:
            smtp.login(gmail_user, gmail_password)
            smtp.send_message(msg)
        print(f'Sendt {len(matches)} påmindelser til {recipient}')
    print('Kontrol gennemført:', TODAY.isoformat())


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--test-dates', action='store_true', help='Test dato-regler uden Dropbox eller e-mail')
    args = parser.parse_args()
    if args.test_dates:
        test_dates()
    else:
        main()
