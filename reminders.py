import os, json, smtplib, ssl, urllib.parse, urllib.request, datetime as dt, calendar
from email.message import EmailMessage

APP_KEY=os.environ['DROPBOX_APP_KEY']
REFRESH=os.environ['DROPBOX_REFRESH_TOKEN']
GMAIL_USER=os.environ['GMAIL_USER']
GMAIL_APP_PASSWORD=os.environ['GMAIL_APP_PASSWORD']
TODAY=dt.date.today()


def post(url, data, headers=None):
    req=urllib.request.Request(url, data=data, headers=headers or {}, method='POST')
    with urllib.request.urlopen(req, timeout=35) as response:
        return response.read()


def subtract_months(day, months):
    total=day.year*12+day.month-1-months
    year, month=divmod(total, 12)
    month+=1
    return dt.date(year,month,min(day.day,calendar.monthrange(year,month)[1]))


def reminder_label(due):
    if TODAY==subtract_months(due,3): return '3 måneder før'
    if TODAY==subtract_months(due,1): return '1 måned før'
    if TODAY==due-dt.timedelta(days=10): return '10 dage før'
    if TODAY==due+dt.timedelta(days=1): return 'Udløbet i går'
    return None


def main():
    token=json.loads(post('https://api.dropboxapi.com/oauth2/token',urllib.parse.urlencode({
        'grant_type':'refresh_token','refresh_token':REFRESH,'client_id':APP_KEY
    }).encode(),{'Content-Type':'application/x-www-form-urlencoded'}))['access_token']
    raw=post('https://content.dropboxapi.com/2/files/download',b'',{
        'Authorization':'Bearer '+token,'Dropbox-API-Arg':json.dumps({'path':'/familie-data.json'})
    })
    records=json.loads(raw)['records']
    recipients={
        '8151213@gmail.com':{'Carsten','Sofie','Erik','Emil'},
        'asskriver@gmail.com':{'Sofie','Erik','Emil'},
    }
    for recipient, persons in recipients.items():
        matches=[]
        for r in records:
            if r.get('person') not in persons or not r.get('due'): continue
            try: due=dt.date.fromisoformat(r['due'])
            except ValueError: continue
            label=reminder_label(due)
            if not label: continue
            kind=r.get('type','')
            certainty=r.get('certainty','confirmed')
            qualifier=(' (vejledende dato)' if certainty=='estimated' else
                       ' (kræver faglig vurdering)' if certainty=='review' else '')
            matches.append(f"• {r['person']}: {kind} – {r.get('name','Registrering')}{qualifier}\n  Dato: {due.strftime('%d.%m.%Y')} · {label}")
        if not matches: continue
        msg=EmailMessage()
        msg['From']=GMAIL_USER
        msg['To']=recipient
        msg['Subject']=f'Familie rejseoverblik – {len(matches)} påmindelse(r)'
        msg.set_content('Automatiske påmindelser fra Familie rejseoverblik:\n\n'+'\n\n'.join(matches)+'\n\nÅbn https://sgcholm.github.io/familie-rejseoverblik/ for detaljer.\n\nBemærk: Vaccinationsfrister er ikke nødvendigvis medicinske udløbsdatoer.')
        with smtplib.SMTP_SSL('smtp.gmail.com',465,context=ssl.create_default_context(),timeout=35) as smtp:
            smtp.login(GMAIL_USER,GMAIL_APP_PASSWORD)
            smtp.send_message(msg)
        print(f'Sendt {len(matches)} påmindelser til {recipient}')
    print('Kontrol gennemført:',TODAY.isoformat())

if __name__=='__main__':main()
