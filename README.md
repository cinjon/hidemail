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
5. Setup page to set times (free: 1 1hr block, paid: 4 half hr blocks) and timezone.
6. Complete backend to remove and add mail from the inbox with the API.
7. Attach the above to a cron that runs on the hour and loops through everyone who fits that tz, adding / removing as required.
8. Implement the IMAP post notifs so that the backend gets a buzz when there's an email.
9. If in a user's block, then let it pass. If not, then hide it.


Later:
- Add in the replies saying "hey this person isn't going to see the email for a while. If this is urgent, you can push it through now by pressing this button."
- Add in a whitelist of people who def get through.