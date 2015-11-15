import telegram
import config
import re
from datetime import datetime, timedelta
from model import *
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from dateutil import parser as dateparser

def registered(required):
    def actual_decorator(func):
        def with_register_checking(self, message):
            user = self.dbsession.query(User).get(message.from_user.id)
            if user == None:
                self.bot.sendMessage(chat_id=message.chat.id, text="這個功能不註冊不能使用喔 OwO+", reply_to_message_id=message.message_id)
                return
            access = user.access
            if required == "admin" and access == "user":
                self.bot.sendMessage(chat_id=message.chat.id, text="這是管理者的特別功能喔", reply_to_message_id=message.message_id)
                return
            return func(self, message)
        return with_register_checking
    return actual_decorator

def no_group(func):
    def with_group_checking(self, message):
        if message.chat.id < 0:
            self.bot.sendMessage(chat_id=message.chat.id, text="這個功能沒辦法在聊天室使用，請跟我私聊。", reply_to_message_id=message.message_id)
            return
        return func(self, message)
    return with_group_checking

def relative_datetime(date):
    day = ""
    # get day

    weekday = ["", "週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    now = datetime.now()

    if date.date() == now.date():
        day = "今天"
    elif date.date() == (now+timedelta(days=1)).date():
        day = "明天"
    elif date.isocalendar()[0] == now.isocalendar()[0] and \
            date.isocalendar()[1] - now.isocalendar()[1] <= 1:
        if (date.isocalendar()[1] - now.isocalendar()[1] == 1):
            day = "下"+weekday[date.isocalendar()[2]]
        else:
            day = weekday[date.isocalendar()[2]]
    elif date.year == now.year:
        day = "%d月%d日" % (date.month, date.day)
    else:
        day = "%d年%d月%d日" % (date.year, date.month, date.day)

    time = date.strftime("%H:%M")

    return "%s %s" % (day, time)

class Flowey:

    # recording time for users sending message for antiflood measures
    users = {}

    @no_group
    def register(self, message):
        chat = message.chat
        from_user = message.from_user

        cmdmatch = re.match(r"^/register(?:@%s)? (\w+)$" % (self.me.username), message.text)
        if cmdmatch == None:
            self.bot.sendMessage(chat_id=chat.id, text="使用方法：\n/register [codename]", reply_to_message_id=message.message_id)
            return
        codename = cmdmatch.group(1)

        existing = self.dbsession.query(User).get(from_user.id)
        if existing == None:
            pass
        elif existing.access == "user" or existing.access == "admin":
            self.bot.sendMessage(chat_id=chat.id, text="你已經註冊過了，你這個笨蛋", reply_to_message_id=message.message_id)
            return
        else:
            self.bot.sendMessage(chat_id=chat.id, text="你這樣會讓管理者很困擾的（丟友善的花瓣）", reply_to_message_id=message.message_id)
            return

        if self.dbsession.query(User).filter(func.lower(User.codename)==func.lower(codename)).count() > 0:
            self.bot.sendMessage(chat_id=chat.id, text="你是幫人家開帳號嗎，去死ㄅ！", reply_to_message_id=message.message_id)

        self.dbsession.add(User(id=from_user.id, name=from_user.username,
            fullname="%s %s" % (from_user.first_name, from_user.last_name),
            codename=codename, date=datetime.now(), access='unconfirmed'))
        self.dbsession.commit()

        admins = self.dbsession.query(User).filter_by(access='admin')
        for admin in admins:
            self.bot.sendMessage(chat_id=admin.id,
                    text="@%s (codename: %s) 想要用花花，請輸入：\n/confirm %d\n以開放他的使用權限" % (from_user.username, codename, from_user.id))

        self.bot.sendMessage(chat_id=chat.id, text="已經通知管理者開通帳號，請耐心等候！", reply_to_message_id=message.message_id)

    @no_group
    @registered("admin")
    def confirm(self, message):
        cmdmatch = re.match(r"^/confirm(?:@%s)? ([0-9]+)$" % (self.me.username), message.text)
        if cmdmatch == None:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="使用方法：\n/confirm [id]\n請參考我發出的通知訊息",
                    reply_to_message_id=message.message_id)
            return
        target_id = int(cmdmatch.group(1))
        user = self.dbsession.query(User).get(target_id)
        if user == None:
            self.bot.sendMessage(chat_id=message.chat.id, text="找不到這個使用者",
                    reply_to_message_id=message.message_id)
            return
        if user.access != "unconfirmed":
            self.bot.sendMessage(chat_id=message.chat.id, text="帳號 %s 已經是開通狀態" % (user.fullname),
                    reply_to_message_id=message.message_id)
            return
        user.access = "user"
        self.dbsession.commit()
        self.bot.sendMessage(chat_id=message.chat.id, text="已經幫 %s 開通帳號！" % (user.fullname),
                reply_to_message_id=message.message_id)
        self.bot.sendMessage(chat_id=target_id, text="您的小花已經開通，歡迎加入！")

    @no_group
    @registered("admin")
    def unregister(self, message):
        cmdmatch = re.match(r"^/unregister(?:@%s)? (\w+)$" % (self.me.username), message.text)
        if cmdmatch == None:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="使用方法：\n/confirm [codename]",
                    reply_to_message_id=message.message_id)
            return
        codename = cmdmatch.group(1)
        user = self.dbsession.query(User).filter(func.lower(User.codename)==func.lower(codename))

        if user.count() == 0:
            self.bot.sendMessage(chat_id=message.chat.id, text="找不到這個使用者",
                    reply_to_message_id=message.message_id)
            return

        user = user.one()
        self.dbsession.delete(user)
        self.dbsession.commit()

        self.bot.sendMessage(chat_id=message.chat.id, text="已經刪除 %s 的帳號！" % (user.fullname),
                reply_to_message_id=message.message_id)
        self.bot.sendMessage(chat_id=user.id, text="管理者已經刪除你的小花帳號，有任何問題不要找我！去找該死的管理者！")

    def _get_activity_by_order(self, id):
        '''
        Get activity by order. A helper function for /join1 or /leave1, etc.
        '''

        return self.dbsession.query(Activity) \
            .filter(Activity.date>datetime.now()) \
            .order_by(Activity.date.asc()).offset(id).limit(1).one_or_none()

    @registered("admin")
    def add(self, message):
        cmdmatch = re.match(r"^/add(?:@%s)? ([0-9\-]+ [0-9\:]+) (.*)" % (self.me.username), message.text)

        if cmdmatch == None:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="使用方法：\n/add 2015-12-15 19:00:00 [名稱]",
                    reply_to_message_id=message.message_id)
            return

        try:
            date = dateparser.parse(cmdmatch.group(1)+" +0800")
            name = cmdmatch.group(2)
        except ValueError:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="日期或時間好像哪裡怪怪的……",
                    reply_to_message_id=message.message_id)
            return

        self.dbsession.add(Activity(name=name, date=date))
        self.dbsession.commit()

        self.bot.sendMessage(chat_id=message.chat.id,
                text="活動「%s」新增完成\n" % (name),
                reply_to_message_id=message.message_id)

    @registered("admin")
    def delete(self, message):
        cmdmatch = re.match(r"^/delete(\d+)(?:@%s)?$" % (self.me.username), message.text) or \
            re.match(r"^/delete(?:@%s)? (\d+)$" % (self.me.username), message.text)

        if cmdmatch == None or int(cmdmatch.group(1)) <= 0:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="使用方法：\n/delete1\n/delete 2",
                    reply_to_message_id=message.message_id)
            return

        order = int(cmdmatch.group(1))
        activity = self._get_activity_by_order(order-1)
        if activity == None:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="找不到任何活動",
                    reply_to_message_id=message.message_id)
            return
        self.dbsession.delete(activity)
        self.dbsession.commit()

        self.bot.sendMessage(chat_id=message.chat.id,
                text="活動「%s」已經刪除" % (activity.name),
                reply_to_message_id=message.message_id)

    @registered("user")
    def activities(self, message):
        activities = self.dbsession.query(Activity) \
            .filter(Activity.date>datetime.now()) \
            .order_by(Activity.date.asc())

        if activities.count() == 0:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="現在沒有任何活動",
                    reply_to_message_id=message.message_id)
            return

        text = ""
        order = 1
        for activity in activities:
            text = text + "%s\n%s (%d)\n要加入請輸入 /join%d\n\n" % \
                    (relative_datetime(activity.date),
                            activity.name, len(activity.attendees), order)
            order += 1

        self.bot.sendMessage(chat_id=message.chat.id,
                text=text,
                reply_to_message_id=message.message_id)

    @registered("user")
    def join(self, message):
        cmdmatch = re.match(r"^/join(\d+)(?:@%s)?$" % (self.me.username), message.text) or \
            re.match(r"^/join(?:@%s)? (\d+)$" % (self.me.username), message.text)

        if cmdmatch == None or int(cmdmatch.group(1)) <= 0:
            self.activities(message)
            return

        order = int(cmdmatch.group(1))
        activity = self._get_activity_by_order(order-1)
        if activity == None:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="找不到任何活動",
                    reply_to_message_id=message.message_id)
            return

        user = self.dbsession.query(User).get(message.from_user.id)
        if user in activity.attendees:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="探員 %s 已在「%s」\n要離開請輸入 /leave%d" % (user.codename, activity.name, order),
                    reply_to_message_id=message.message_id)
            return

        activity.attendees.append(user)
        self.dbsession.commit()
        self.bot.sendMessage(chat_id=message.chat.id,
                text="探員 %s 已加入「%s」" % (user.codename, activity.name),
                reply_to_message_id=message.message_id)

    @registered("user")
    def leave(self, message):
        cmdmatch = re.match(r"^/leave(\d+)(?:@%s)?$" % (self.me.username), message.text) or \
            re.match(r"^/leave(?:@%s)? (\d+)$" % (self.me.username), message.text)

        if cmdmatch == None or int(cmdmatch.group(1)) <= 0:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="使用方法：\n/leave\n/leave 2",
                    reply_to_message_id=message.message_id)
            return

        order = int(cmdmatch.group(1))
        activity = self._get_activity_by_order(order-1)
        if activity == None:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="找不到任何活動",
                    reply_to_message_id=message.message_id)
            return

        user = self.dbsession.query(User).get(message.from_user.id)
        if not(user in activity.attendees):
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="探員 %s 不在「%s」\n要加入請輸入 /join%d" % (user.codename, activity.name, order),
                    reply_to_message_id=message.message_id)
            return

        activity.attendees.remove(user)
        self.dbsession.commit()
        self.bot.sendMessage(chat_id=message.chat.id,
                text="探員 %s 已離開「%s」" % (user.codename, activity.name),
                reply_to_message_id=message.message_id)

    @no_group
    @registered("admin")
    def op(self, message):
        cmdmatch = re.match(r"^/op(?:@%s)? (\w+)$" % (self.me.username), message.text)
        if cmdmatch == None:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="使用方法：\n/op [codename]",
                    reply_to_message_id=message.message_id)
            return
        codename = cmdmatch.group(1)
        user = self.dbsession.query(User).filter(func.lower(User.codename)==func.lower(codename))

        if user.count() == 0:
            self.bot.sendMessage(chat_id=message.chat.id, text="找不到這個使用者",
                    reply_to_message_id=message.message_id)
            return

        user = user.one()
        self.dbsession.access = "admin"
        self.dbsession.commit()

        self.bot.sendMessage(chat_id=message.chat.id, text="已經將 %s 的權限改為管理者。" % (user.fullname),
                reply_to_message_id=message.message_id)

    @no_group
    @registered("admin")
    def deop(self, message):
        cmdmatch = re.match(r"^/deop(?:@%s)? (\w+)$" % (self.me.username), message.text)
        if cmdmatch == None:
            self.bot.sendMessage(chat_id=message.chat.id,
                    text="使用方法：\n/op [codename]",
                    reply_to_message_id=message.message_id)
            return
        codename = cmdmatch.group(1)
        user = self.dbsession.query(User).filter(func.lower(User.codename)==func.lower(codename))

        if user.count() == 0:
            self.bot.sendMessage(chat_id=message.chat.id, text="找不到這個使用者",
                    reply_to_message_id=message.message_id)
            return

        user = user.one()
        self.dbsession.access = "user"
        self.dbsession.commit()

        self.bot.sendMessage(chat_id=message.chat.id, text="已經將 %s 的權限改為使用者。" % (user.fullname),
                reply_to_message_id=message.message_id)

    def help(self, message):
        user = self.dbsession.query(User).get(message.from_user.id)
        print(user)
        if user == None:
            self.bot.sendMessage(chat_id=message.chat.id, text="你尚未註冊，要使用此系統請輸入\n/register\n註冊",
                reply_to_message_id=message.message_id)
        elif user.access == "admin":
            self.bot.sendMessage(chat_id=message.chat.id, text='''以下為管理者可使用的功能：
/confirm - 審核某人使用此系統
/unregister - 取消某人權限
/add - 新增活動
/delete - 刪除活動
/join - 加入活動
/leave - 離開活動
/op - 新增某人管理者權限
/deop - 取消某人管理者權限''',
                reply_to_message_id=message.message_id)
        elif user.access == "user":
            self.bot.sendMessage(chat_id=message.chat.id, text='''以下為一般使用者可使用的功能：
/join - 加入活動
/leave - 離開活動''',
                reply_to_message_id=message.message_id)
        elif user.access == "unconfirmed":
            self.bot.sendMessage(chat_id=message.chat.id, text="請等管理者開通你使用花花的權限，感謝 owo",
                reply_to_message_id=message.message_id)

    def dispatch_command(self, message):
        cmdmatch = re.match(r"/(\w+)(?:@%s)?" % (self.me.username), message.text)
        if cmdmatch == None:
            return
        cmd = cmdmatch.group(1)
        if cmd == "register":
            self.register(message)
        elif cmd == "confirm":
            self.confirm(message)
        elif cmd == "unregister":
            self.unregister(message)
        elif cmd == "add":
            self.add(message)
        elif cmd.find("delete") == 0:
            self.delete(message)
        elif cmd == "activities":
            self.activities(message)
        elif cmd.find("join") == 0:
            self.join(message)
        elif cmd.find("leave") == 0:
            self.leave(message)
        elif cmd == "op":
            self.op(message)
        elif cmd == "deop":
            self.deop(message)
        elif cmd == "help":
            self.help(message)

    def preparedb(self):
        dbengine = create_engine(config.dburi)
        FloweyBase.metadata.create_all(dbengine)
        Session = sessionmaker(bind=dbengine)
        self.dbsession = Session()

    def start(self, token):
        self.bot = telegram.Bot(token=token)
        self.me = self.bot.getMe()

        self.preparedb()

        #try:
        #    self.last_update = self.bot.getUpdates(timeout=30)[-1].update_id
        #except IndexError:
        self.last_update = 0

        while True:
            updates = self.bot.getUpdates(offset=self.last_update + 1, timeout=30)
            for update in updates:
                self.last_update = update.update_id
                if (datetime.now() - update.message.date) > timedelta(seconds=60):
                    print("Old message received")
                    continue
                if (update.message.from_user.id in self.users) and (update.message.date - self.users[update.message.from_user.id]['last_date']) < timedelta(seconds=3):
                    print("Flooding detected")
                    continue
                print(update)
                self.users[update.message.from_user.id] = {'last_date':update.message.date}
                self.dispatch_command(update.message)

if __name__ == '__main__':
    flowey = Flowey()
    flowey.start(config.token)
