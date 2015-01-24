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
X 1. Get the batching working.
X 2. Get it working in Heroku.
X 3. Attach it to my own email.
X 3a. Need checks on all the functions so we don't break people's email.
X 4. Add account_type on users (probably a bijective Account model)
   - account_type is what kind of account, e.g. inactive, unpaid, monthly, six week, w/e
X 5. Add pricing [page] and Stripe Connect using that Account model
X 6. Dropdown in top right will let you see what email it is and let you logout.
X 7. About page.
8. Cute mascot. A hamster obviously.
X 9. Something needs to check that the account info is complete before adding the inbox to the queue.
X 10. Need to figure out how to store account date of activation and charges.
X 11. Split inbox into customer and inbox so that a customer can have multiple inboxes. this way, they can add inboxes without paying more.
X 12. Add Stripe Subscription.
X 13. Think through the flow, maybe add an activate button after signing up and paying. --> No activate button. Once you pay, you are activated.
X 14. Email account - cinjon@mailboxflow.com
X 15. SSL
X 16. Stripe Tests
17. Error Reporting to Users
18. Using my own account.
X 19. FAQ
X 20. Cron nightly to archive old email --> Fixed this by doing it at point of show / hide mail
X 21. Fix UserData saving
X 22. Time selection:
X    - Change the user creation to not make timeblocks
X    - Instead have timeblocks be a string model, e.g "9,10,11,12,18,19,20" --> Instead did proper timeblocks.
X    - Parse it on the client's side and show it on a calendar set.
X 23. Can change the set of times and then press save to save them.
X 24. Need an activate button once you have an acceptable account (free, trial, monthly, break)
X 25. Instructions on how to use the calendar
26. Option to take a sabbatical --> need a start date and end date.
27. Need a nightly cron that checks for people ending sabbaticals and trials. --> Can do this with APScheduler
X 28. Change archive logic to have is_init_archiving, is_init_archive_complete. Turn on first when archiving. Turn on second when complete. Turn off both when inactivated.
29. Does it work on mobile?


Later:
- Add in the replies saying "hey this person isn't going to see the email for a while. If this is urgent, you can push it through now by pressing this button."
