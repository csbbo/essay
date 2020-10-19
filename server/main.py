#! /usr/bin/env python3

from flask import Flask, render_template, request, redirect, url_for, make_response, jsonify
from flask_pymongo import PyMongo, DESCENDING
from bson import ObjectId
import datetime, sys
import pdfkit
from urllib.parse import quote
from apscheduler.schedulers.blocking import BlockingScheduler
import jinja2
import base64
import hashlib
import logging

from email import encoders
from email.header import Header
from email.mime.text import MIMEText
from email.utils import parseaddr, formataddr
import smtplib

from conf import settings
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config["MONGO_URI"] = settings.MONGODB_ADDR + "/essay"
mongo = PyMongo(app)

# utils
def _format_addr(s):
    name, addr = parseaddr(s)
    return formataddr((Header(name, 'utf-8').encode(), addr))

def send_email(to_list, subject, html):
    msg = MIMEText(html, 'html', 'utf-8')
    msg['From'] = _format_addr('每日comment <%s>' % settings.EMAIL_FROM_ADDR)
    msg['To'] = ';'.join([_format_addr('你好! <%s>' % addr) for addr in to_list])
    msg['Subject'] = Header(subject, 'utf-8').encode()

    try:
        server = smtplib.SMTP(settings.EMAIL_SMTP_SERVER, settings.EMAIL_PORT)
        server.starttls()
        server.set_debuglevel(1)
        server.login(settings.EMAIL_FROM_ADDR, settings.EMAIL_PASSWORD)
        r = server.sendmail(settings.EMAIL_FROM_ADDR, to_list, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(e)
        return False

def pub_sub_content():
    emails = mongo.db.subscribe.find()
    emails = [e['email'] for e in emails]

    today = datetime.datetime.today().date().strftime('%Y%m%d')
    article = mongo.db.article.find_one({'publish_date': today})
    if article is None:
        article = mongo.db.article.find_one({'publish_date': None})
        if article is not None:
            article['publish_date'] = today
            mongo.db.article.save(article)
    emails = ['chshbox@gmail.com']
    if article is not None:
        env = jinja2.Environment(loader = jinja2.FileSystemLoader('./templates'))
        content = env.get_template('send_subscrip_success_template.html').render(**article)
        is_success = send_email(emails, 'daliy subscrip', content)
        if not is_success:
            for email in emails:
                send_email([email], 'daliy subscrip', content)

def scheduler_task():
    scheduler = BlockingScheduler()
    scheduler.add_job(pub_sub_content, 'cron', day_of_week='0-6', hour=7, minute=0, second=0)
    scheduler.start()

# route
@app.route('/article_add', methods=['GET', 'POST'])
def article_add():
    if request.method == 'GET':
        return render_template('article_add.html')

    secret = request.form.get('secret')
    if secret != 'article_add01':
        return redirect(url_for('article_add'))

    author = request.form.get('author')
    title = request.form.get('title')
    content = request.form.get('content')
    article = {
        'author': author,
        'title': title,
        'content': content,
        'create_time': datetime.datetime.now(),
        'publish_date': None,
        'words': len(content),
        'reads': 0,
        'likes': 0,
        'pdf_downloads': 0
    }
    article = mongo.db.article.insert_one(article)
    return redirect(url_for('article_get', id=article.inserted_id))

@app.route('/article_delete', methods=['GET', 'POST'])
def article_delete():
    if request.method == 'GET':
        return render_template('article_delete.html')

    secret = request.form.get('secret')
    if secret != 'article_delete01':
        return redirect(url_for('article_delete'))

    id = request.form.get('id')
    collection = mongo.db.article
    article = collection.find_one({'_id': ObjectId(id)})
    collection.remove(article)
    return redirect(url_for('article_delete'))

@app.route('/article/<id>', methods=['GET'])
def article_get(id):
    article = mongo.db.article.find_one({'_id': ObjectId(id)})
    article['reads'] += 1
    mongo.db.article.save(article)

    comments = mongo.db.comment.find({'article_id': ObjectId(id)}).sort([["create_time", DESCENDING]])
    resp_data = {
        '_id': article['_id'],
        'title': article['title'],
        'content': article['content'],
        'comments': comments if comments.count() > 0 else None
    }
    return render_template('article_get.html', **resp_data)

@app.route('/pdfdownload/<id>', methods=['GET'])
def pdfdownload(id):
    article = mongo.db.article.find_one({'_id': ObjectId(id)})
    article['pdf_downloads'] += 1
    mongo.db.article.save(article)
    filename = article['title'] + '.pdf'

    pdf_html =  render_template('pdf_template.html', **article)
    pdf = pdfkit.from_string(pdf_html, False)

    resp = make_response(pdf)
    resp.headers['Access-Control-Expose-Headers'] = 'Content-Disposition'
    resp.headers['Content-Disposition'] = f"attachment;filename={quote(filename)}"
    resp.headers["Content-Type"] = 'application/octet-stream'
    return resp

@app.route('/article_list/', methods=['GET'])
def article_list():
    search = request.args.get('search', None)
    if search is None:
        articles = mongo.db.article.find({'publish_date': {'$ne': None}}).sort([["publish_date", DESCENDING]])
    else:
        filter = {"$or": [
                {"title": {'$regex': search}},
                {"author": {'$regex': search}},
                {"content": {'$regex': search}},
            ]
        }
        articles = mongo.db.article.find(filter).sort([["publish_date", DESCENDING]])

    resp = []
    for article in articles:
        data = {
            'id': article['_id'],
            'title': article['title'],
            'author': article['author'],
            'content': article['content'][:100] + '...',
            'publish_date': datetime.datetime.strptime(article['publish_date'], '%Y%m%d').strftime('%Y-%m-%d'),
            'words': article['words'],
            'pdf_downloads': article['pdf_downloads'],
            'likes': article['likes'],
            'reads': article['reads']
        }
        resp.append(data)
    return render_template('article_list.html', **{'articles': resp})

@app.route('/', methods=['GET'])
def home():
    today = datetime.datetime.today().date().strftime('%Y%m%d')
    collection = mongo.db.article

    article = collection.find_one({'publish_date': today})
    if article is None:
        article = collection.find_one({'publish_date': None})
        if article is not None:
            article['publish_date'] = today
            collection.save(article)
        else:
            article = collection.find_one()
    if article is None:
        article = {
            'title': '空空如也~',
            '_id': '#'
        }
    return render_template('home.html', **article)


@app.route('/email_subscribe', methods=['POST'])
def email_subscribe():
    email_addr = request.form.get('email')
    email = mongo.db.subscribe.find_one({'email': email_addr})
    resp = {
            "err": None,
            "msg": None
    }
    if email is None:
        email_base64 = base64.b64encode(bytes(email_addr, encoding='utf-8'))
        secret = hashlib.sha224(email_base64).hexdigest()

        email_base64 = str(email_base64, encoding='utf-8')
        confirm_addr = settings.SERVER_ADDR + url_for('email_confirm', code = (email_base64 + secret))
        html = render_template('send_subscrip_success_template.html', **{'addr': confirm_addr})
        send_email([email_addr], '订阅通知', html)
    else:
        resp['err'] = 'err'
        resp['msg'] = '该邮箱已订阅!'
    return jsonify(resp)

@app.route('/email_confirm', methods=['GET'])
def email_confirm():
    code = request.args.get('code', None)
    resp = {
        "err": 'err',
        "msg": 'url验证失败!'
    }
    if not code:
        return jsonify(resp)
    if len(code) <= 56:
        return jsonify(resp)

    email_base64 = bytes(code[:-56], encoding='utf-8')
    secret = code[-56:]
    if secret != hashlib.sha224(email_base64).hexdigest():
        return jsonify(resp)

    email_addr = str(base64.b64decode(email_base64), encoding='utf-8')

    if mongo.db.subscribe.find_one({'email': email_addr}):
        resp['msg'] = '该邮箱已订阅!'
        return jsonify(resp)

    subscribe = {
        'email': email_addr,
        'create_time': datetime.datetime.now(),
    }
    mongo.db.subscribe.insert_one(subscribe)
    return redirect(url_for('home'))

@app.route('/about', methods=['GET'])
def about():
    if request.method == 'GET':
        return render_template('about.html')

@app.route('/comment', methods=['POST'])
def comment():
    resp = {
        "err": 'err',
        "msg": 'id不能为空'
    }

    ip = request.remote_addr
    article_id = request.form.get('article_id')
    content = request.form.get('content')
    if article_id is None:
        return jsonify(resp)
    if content is None:
        resp['msg'] = '评论内容不能为空'
        return jsonify(resp)
    
    comment = {
        'article_id': ObjectId(article_id),
        'ip': ip,
        'content': content,
        'create_time': datetime.datetime.now(),
        'words': len(content),
    }
    comment = mongo.db.comment.insert_one(comment)
    del resp['msg']
    resp['err'] = None
    resp['data'] = None
    return jsonify(resp)

@app.route('/like', methods=['POST'])
def like():
    ip = request.remote_addr
    article_id = request.form.get('article_id')

    resp = {
        "err": 'err',
        "msg": 'id不能为空'
    }

    if article_id is None:
        return jsonify(resp)

    today = datetime.datetime.today().date().strftime('%Y%m%d')
    filter = {
        'article_id': ObjectId(article_id),
        'ip': ip,
        'create_date': today
    }
    like = mongo.db.like.find_one(filter)
    if like is not None:
        resp['msg'] = '知道你很喜欢这篇文章，但一天只能点赞一次哦!'
        return jsonify(resp)

    like_data = {
        'article_id': ObjectId(article_id),
        'ip': ip,
        'create_date': today,
        'create_time': datetime.datetime.now()
    }
    mongo.db.like.insert_one(like_data)
    article = mongo.db.article.find_one({'_id': ObjectId(article_id)})
    article['likes'] = article['likes'] + 1
    mongo.db.article.save(article)

    del resp['msg']
    resp['err'] = None
    resp['data'] = '点赞成功,谢谢喜欢!'
    return jsonify(resp)


if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[-1] == 'scheduler':
        scheduler_task()

    app.debug = settings.DEBUG_MODEL
    app.run(host='0.0.0.0', port=settings.SERVER_PORT)
