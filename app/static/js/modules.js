'use strict';

var lsKey = 'localmbxflow';
var stripeTestPK = 'pk_test_gLDeXwxIEjBhEpHwSlpE25T0'
var stripeLivePK = 'pk_live_puq7AjfvQJkAfND9Ddmghww1'
var stripePK = stripeLivePK
var accountTypes = {0:'Inactive', 1:'Free', 2:'Subscription', 3:'Week Trial'}
var errorMessages = {
  'stripe_invalid_parameters':"Sorry. There was an error processing your card. Please try again.",
  'stripe_auth_fail':"Sorry. We had trouble connecting to Stripe. Please try again.",
  'stripe_network_fail':"Sorry. We had trouble connecting to Stripe's network. Please try again.",
  'stripe_failed':"Sorry. There was an error handling your card. Please try again.",
  'stripe_maybe_not':"Sorry. We hit an error completing the payment. Please try again."
}

angular.module('HideMail', ['hidemailServices', 'hidemailDirectives', 'hidemailFilters', 'angular-loading-bar', 'satellizer'])
  .controller('navBar', function($scope, $http, $auth, $location, LocalStorage, UserData) {
    $scope.$watch(function() { return UserData.getUser() }, function(newValue) {
      $scope.user = newValue;
    }, true)

    getUser(UserData, $http, $auth, function(user) {
      $scope.user = user;
    });

    $scope.go = function(path) {
      $location.path(path);
    }

    $scope.getAccountType = function(accountInt) {
      return accountTypes[accountInt]
    }

    $scope.$watch('user', function(newVal) {
      if (newVal) {
        $scope.userWelcome = newVal.name.split(' ')[0]
        if (!$scope.userWelcome) {
          $scope.userWelcome = 'Welcome';
        }
      } else {
        $scope.userWelcome = "Get Started"
      }
    })

    $scope.logout = function() {
      UserData.setUser(null)
      $auth.logout();
    }

    $scope.oauth = function() {
      var state = {};
      if ($scope.user) {
        state['customer'] = $scope.user.customer_id;
        state['tzOffset'] = $scope.user.currTzOffset;
      } else {
        state['customer'] = null;
        state['tzOffset'] = getTzOffset();
      }

      $auth.authenticate('google', {'state':state}).then(function(response) {
        if (response.data.success) {
          var user = response.data.user;
          UserData.setUser(user);
          if (user.isActive) {
            $scope.go('/me')
          } else {
            $scope.go('/plans')
          }
        } else {
          console.log('Failed to authenticate.'); //Report to user
        }
      })
    }
  })
  .controller('home', function($scope, $http, $auth, $location, UserData) {
    getUser(UserData, $http, $auth, function(user) {
      UserData.setUser(user);
      $scope.user = user;
    });

    $scope.introductions = [
      "We accomplish quality work when we reach a state of flow.",
      "Today's connectedness can make this difficult."
    ]
    $scope.information = [
      "mailboxFlow lets you select periods to respond to your email.",
      "At all other times, it hides your inbox. From all devices."
    ]
  })
  .controller('plans', function($scope, $http, $auth, $location, LocalStorage, Post, UserData) {
    $scope.alert = null;

    $http.get('/get-stripe-pk').then(function(response) {
      $scope.handler = StripeCheckout.configure({
        key: response.data.stripe_pk,
        //       image: '/make-some-image.png,
        token: function(token) {
          token['selection'] = $scope.selection
          token['customer_id'] = $scope.user.customer_id
          Post.postPayment(token).then(function(response) {
            var data = response.data;
            if (data.success) {
              setUser(data.user);
              $location.path('/me')
            } else {
              $scope.alert = {'message':errorMessages[data.errorType], 'type':'danger'}
              if (!$scope.alert.message) {
                $scope.alert.message = 'Sorry. ' + data.errorType + ' Please try again.'
              }
            }
          });
        }
      });
    })

    var setUser = function(user) {
      $scope.user = user;
      UserData.setUser(user);
    }

    getUser(UserData, $http, $auth, function(user) {
      console.log('in plans this is the user')
      console.log(user)
      setUser(user);
    })

    $scope.plans = [
      {
        selection:'monthly',
        description:'Monthly Subscription', price:500,
        isSubscription:true, period:'month',
        url:'/static/partials/plan.html',
        title:"Monthly Service",
        details:[
          "A latte at Sightglass.",
          "Or focus and deeper thought.",
          "Our Top Choice."
        ]},
      {
        selection:'trial',
        description:'One Week Trial', price:500,
        url:'/static/partials/plan.html',
        title:"One Week Red Pill",
        details:[
          "Treat yourself.",
          "A fine beer at Monk's Kettle.",
          "Or the opportunity to flow."
        ]
      }
    ]

    $scope.buy = function(plan) {
      $scope.closeAlert();
      $scope.selection = plan.selection // Is there a way to add this info to the token?
      var description = plan.description;
      var price = plan.price;
      $scope.handler.open({
        name: 'mailboxFlow',
        description: description,
        amount: price,
        email: $scope.user.inboxes[0].email
      })
    }

    $scope.closeAlert = function() {
      $scope.alert = null;
    }

    $scope.oauth = function() {
      var state = {};
      state['customer'] = null;
      state['tzOffset'] = getTzOffset();

      $auth.authenticate('google', {'state':state}).then(function(response) {
        if (response.data.success) {
          $scope.user = response.data.user;
          LocalStorage.set(lsKey, $scope.user)
          UserData.setUser($scope.user)
          $location.path('/plans')
        } else {
          console.log('Failed to authenticate.');
        }
      })
    }
  })
  .controller('profile', function($scope, $http, Post, $timeout, $auth, $location, UserData) {
    console.log('in porfile')
    $scope.introductions = [
      "You can change periods once every three days.",
      "You can change the timezone when you're in a new place."
    ]

    $scope.clock = Date.now()
    $scope.tickInterval = 1000
    var tick = function() {
      $scope.clock = Date.now()
      $timeout(tick, $scope.tickInterval);
    }
    $timeout(tick, $scope.tickInterval);

    $scope.$watch(function() { return UserData.getUser() }, function(newValue) {
      if (newValue && !newValue.timeblocks) {
        console.log('in the watch func')
        getTimeInfo(newValue)
      }
    }, true)

    var getTimeInfo = function(user) {
      if (user) {
        setTimeInfo(user);
      } else {
        getUser(UserData, $http, $auth, function(user) {
          console.log('callback')
          if (!user) {
            $location.path('/')
          } else {
            setTimeInfo(user);
          }
        })
      }
    }
    getTimeInfo(null)

    var setTimeInfo = function(user) {
      console.log('getting time info')
      $http.get('/api/get-time-info/' + user.customer_id).then(function(response) {
        var data = response.data;
        if (data.success) {
          console.log(data.user);
          setUser(data.user);
        } else {
          console.log('err, user time info went wrong.') // Report back error
        }
      })
    }

    $scope.allInboxes = null;
    var setUser = function(user) {
      console.log('profile setting user')
      $scope.user = user;
      UserData.setUser(user);
      if ($scope.user.inboxes.length > 0) {
        $scope.allInboxes = 'Your Inboxes: ' + $scope.user.inboxes.map(function(inbox) {return inbox.email;}).join(', ');
      } else {
        $scope.allInboxes = null;
      }

      if ($scope.user.lastTzAdj) {
        $scope.user.lastTzAdj = new Date($scope.user.lastTzAdj)
      }
      if ($scope.user.lastTbAdj) {
        $scope.user.lastTbAdj = new Date($scope.user.lastTbAdj)
      }
      console.log('setting user...')
      setBlocks($scope.user)
    }

    var setBlocks = function(user) {
      $scope.blocks = user.timeblocks.map(function(block) {
        var period = 'pm'
        var length = block.length
        var hour = parseInt(block.start)/60
        if (hour < 12) {
          period = 'am'
        }
        if (hour > 12) {
          hour = hour - 12;
        }
        if (hour == 0) {
          hour = 12;
        }
        return {'length':length, 'time':hour + ' ' + period}
      })
      $scope.times = $scope.blocks.map(function(block) { return block.time })
    }

    $scope.setTimezone = function() {
      var tzOffset = getTzOffset();
      Post.postTimezone($scope.user.customer_id, tzOffset).then(function(response) {
        var data = response.data;
        if (data.success) {
          setUser(data.user);
        } else {
          console.log('err, failure in posting timezone'); // report back to user
        }
      })
    }

    $scope.timezoneOffset = function() {
      if (!$scope.user || !$scope.user.lastTzAdj || $scope.canSetTimezone()) {
        return offsetString(-1 * getTzOffset() / 60);
      } else {
        return offsetString(-1 * $scope.user.currTzOffset / 60);
      }
    }
    var offsetString = function(offset) {
      if (offset >= 0) {
        return "+" + offset;
      } else {
        return "-" + -1*offset;
      }
    }

    $scope.getTimezoneDesc = function() {
      if ($scope.user && !$scope.user.lastTzAdj) {
        return "Click to set timezone to:"
      } else if ($scope.canSetTimezone()) {
        return "Click to change timezone to:"
      } else {
        return "Timezone set to:"
      }
    }

    $scope.canSetTimezone = function() { //This gets called every single time the clock ticks
      return $scope.user && (!$scope.user.lastTzAdj || $scope.user.currTzOffset != getTzOffset());
    }
    $scope.canSetTimeblocks = function() {
      if (!$scope.user) {
        return false;
      }
      var time = $scope.user.lastTbAdj
      return !time || is_out_of_range(
        time, new Date(new Date() - 1000*60*60*24*3), new Date(new Date() - 1000*60*15)
      )
    }
    var is_out_of_range = function(time, beg, end) {
      return time < beg || time > end
    }

    $scope.getBlockDescription = function(block) {
      if ($scope.canSetTimeblocks()) {
        return 'Select to change period ' + ($scope.blocks.indexOf(block) + 1) + ':'
      } else {
        return 'Period start time:'
      }
    }

    $scope.getAvailableTimes = function(blockTime) {
      return allTimes.filter(function(time) { return time == blockTime || $scope.times.indexOf(time) == -1 })
    }

    $scope.updateBlocks = function() {
      var timeblocks = $scope.blocks.map(function(block) {
        var parts = block.time.split(' ');
        var period = parts[1].toLowerCase()
        var hour = parseInt(parts[0])
        var start_time = 0;
        if (period == 'am') {
          if (hour < 12) {
            start_time = hour * 60;
          }
        } else if (period == 'pm') {
          start_time = hour * 60;
          if (hour < 12) {
            start_time += 12*60;
          }
        }
        return {length:block.length, start:start_time};
      })

      Post.postBlocks($scope.user.customer_id, timeblocks).then(function(response) {
        var data = response.data;
        if (data.success) {
          setUser(data.user);
        } else {
          console.log('err, failure in posting blocks');
        }
      })
    }
  })
  .controller('faq', function($scope) {
    $scope.faq = [
      {'question':"What if I don't like the time periods I choose?",
       'answer':"Change them. You can do this once every three days."},
      {'question':"What happens when I'm in a new timezone?",
       'answer':"Visit your profile and there will be an option to adjust it."},
      {'question':"I have 17,000 emails. Are you really going to hide them all from me?",
       'answer':"No. We archive everything older than two weeks. Then we hide your emails from you."},
      {'question':"Wait, what? How do I find my emails if they're archived?",
       'answer':"Search for them in the top bar. This is probably what you do anyways."},
      {'question':"What if I miss something important?",
       'answer':"It's possible. It's more likely though that it was someone else putting an item on the top of your to-do list."},
      {'question':"Why did you make this?",
       'answer':"We made this. No one builds anything alone. I got a lot of help along the way."},
      {'question':"Ok, but really, what was your motivation and does it involve selling my data?",
       'answer':"I built this because I wanted to free myself from constantly checking email and more easily settle into a flow when working. I figured others want that as well. I charge for this so that I don't need to sell your data."},
      {'question':"But couldn't you be selling my data as well?",
       'answer':"It's possible, but I think that it would be really bad if I was and others found out. So I'm not and I feel pretty good about building something that folks want to use."}
      ]
  })
  .config([
    '$routeProvider', '$locationProvider', '$authProvider',
    function($routeProvider, $locationProvider, $authProvider, $window) {
      $routeProvider
	.when('/', {
	  templateUrl: '/static/partials/home.html',
          controller: 'home'
	})
        .when('/me', {
          templateUrl: '/static/partials/profile.html',
          controller: 'profile'
        })
        .when('/plans', {
          templateUrl: '/static/partials/plans.html',
          controller: 'plans'
        })
        .when('/faq', {
          templateUrl: '/static/partials/faq.html',
          controller: 'faq'
        })
	.otherwise({
	  redirectTo: '/'
	});
      $locationProvider.html5Mode(true);
      $authProvider.google({
        clientId: '25163235185-htbit88rhvikp405ccsgoh31cdr3pjim.apps.googleusercontent.com'
      });
    }
  ]);

var getUser = function(userData, http, auth, callback) {
  console.log('getting user')
  var userDataUser = userData.getUser();
  if (userDataUser) {
    console.log('userdatauser')
    console.log(userDataUser)
    return userDataUser;
  }

  var userToken = auth.getToken()
  if (userToken) {
    http.get('/api/user-from-token/' + userToken).then(function(response) {
      var data = response.data;
      if (data.success) {
        if (data.user) {
          console.log('calling user')
          console.log(data.user);
          callback(data.user);
        } else if (data.token == false) {
          auth.logout()
          callback(null)
        }
      } else {
        callback(null);
      }
    })
  } else {
    callback(null);
  }
}

var getTzOffset = function() {
  return (new Date()).getTimezoneOffset()
}

var redirectIfNotArgs = function(params, $location) {
  for (var param in params) {
    if (!params[param] || params[param] == '') {
      $location.path('/')
    }
  }
}

var numToWords = function(num) {
  if (num == 60) {
    return 'Sixty';
  }
}

function getAllTimes() {
  var allHours = [12].concat(Array.apply(null, Array(11)).map(function (_, i) { return i+1 }));
  var temp = allHours.map(function(hour) { return hour.toString() + ' am' }).concat(allHours.map(function(hour) { return hour.toString() + ' pm' }));
  var ret = [];
  for (var index = 0; index < temp.length; index++) {
    var firstValue = temp[index];
    var secondIndex = index + 1;
    if (secondIndex == temp.length) {
      secondIndex = 0;
    }
    var secondValue = temp[secondIndex];
    ret.push(firstValue + " - " + secondValue);
  }
  return ret;
}
// var allTimes = getAllTimes();
var allHours = [12].concat(Array.apply(null, Array(11)).map(function (_, i) { return i+1 }));
var allTimes = allHours.map(function(hour) { return hour.toString() + ' am' }).concat(allHours.map(function(hour) { return hour.toString() + ' pm' }));

window.mobilecheck = function() {
  var check = false;
  (function(a){if(/(android|bb\d+|meego).+mobile|avantgo|bada\/|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|mobile.+firefox|netfront|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|series(4|6)0|symbian|treo|up\.(browser|link)|vodafone|wap|windows (ce|phone)|xda|xiino/i.test(a)||/1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\-(n|u)|c55\/|capi|ccwa|cdm\-|cell|chtm|cldc|cmd\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\-s|devi|dica|dmob|do(c|p)o|ds(12|\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\-|_)|g1 u|g560|gene|gf\-5|g\-mo|go(\.w|od)|gr(ad|un)|haie|hcit|hd\-(m|p|t)|hei\-|hi(pt|ta)|hp( i|ip)|hs\-c|ht(c(\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\-(20|go|ma)|i230|iac( |\-|\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\/)|klon|kpt |kwc\-|kyo(c|k)|le(no|xi)|lg( g|\/(k|l|u)|50|54|\-[a-w])|libw|lynx|m1\-w|m3ga|m50\/|ma(te|ui|xo)|mc(01|21|ca)|m\-cr|me(rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\-2|po(ck|rt|se)|prox|psio|pt\-g|qa\-a|qc(07|12|21|32|60|\-[2-7]|i\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\-|oo|p\-)|sdk\/|se(c(\-|0|1)|47|mc|nd|ri)|sgh\-|shar|sie(\-|m)|sk\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\-|v\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\-|tdg\-|tel(i|m)|tim\-|t\-mo|to(pl|sh)|ts(70|m\-|m3|m5)|tx\-9|up(\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|yas\-|your|zeto|zte\-/i.test(a.substr(0,4)))check = true})(navigator.userAgent||navigator.vendor||window.opera);
  return check;
}