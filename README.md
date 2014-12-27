A. Website where people can OAuth their gmail
B. Once OAuthed, they can set their times and timezones.
C. With times in hand, move all of the email with tag INBOX to tag HideMyMail.
D. If it’s a time when they want to check email, move all email with tag HideMyMail to tag INBOX.
E. Add in an IMAP hook that gets a notif whenever a new email comes in. If it’s outside of one of the ranges, hide it by moving to the diff inbox.


Step by step:
X 1. Figure out models
    - Inbox represents a person. It's not users as much as it is inboxes because they're all connected to GMail. Many to many with Timezones. One to many with Timeblocks. Has an auth token and user email and something else related to gmail acc ... what?
    - Timeblock represents a chunk of time that they can see their email. It's of a certain length in minutes and has a start time given in minutes since the day started.
    - Timezone represents a timezone offset from GMT (UTC?).
X 2. Set up postgres DB
X 3. Put up dummy page to test OAuth Access
X 4. Setup OAuth to get access for Gmail API scopes
X 5. Setup page to set times (free: 1 1hr block, paid: 4 half hr blocks) and timezone.
X 6. Complete backend to remove and add mail from the inbox with the API.
X 7. Attach the above to a cron that runs on the hour and loops through everyone who fits that tz, adding / removing as required.
X9. If in a user's block, then let it pass. If not, then hide it.

Sweet. Next steps:
1. Get the batching working.
2. Get it working in Heroku.
3. Attach it to my own email.
X 3a. Need checks on all the functions so we don't break people's email.
4. Add account_type on users (probably a bijective Account model)
   - account_type is what kind of account, e.g. inactive, unpaid, monthly, six week, w/e
5. Add pricing [page] and Stripe Connect using that Account model
6. Dropdown in top right will let you see what email it is and let you logout.
X 7. About page.
8. Cute mascot. A hamster obviously.
9. Something needs to check that the account info is complete before adding the inbox to the queue.

What's necessary to pushing it out to people? 1,2,3,4
What's necessary to getting people to apy for it? 5,7

Later:
- Add in the replies saying "hey this person isn't going to see the email for a while. If this is urgent, you can push it through now by pressing this button."
- Add in a whitelist of people who def get through.