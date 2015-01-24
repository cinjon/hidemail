
'use strict';

var accountTypes = {0:'Inactive', 1:'Free', 2:'Subscription', 3:'Week Trial'}

angular.module('HideMail', ['hidemailServices', 'hidemailDirectives', 'hidemailFilters', 'angular-loading-bar', 'satellizer'])
  .controller('navBar', function($scope, $http, $auth, $location, UserData) {
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
        }
      })
    }
  })
  .controller('home', function($scope) {
    $scope.introductions = [
      "We accomplish quality work when we reach a state of flow.",
      "Today's connectedness can make this difficult."
    ]
    $scope.information = [
      "mailboxFlow lets you select periods to respond to your email.",
      "At all other times, it hides your inbox. From all devices."
    ]
  })
  .controller('plans', function($scope, $http, $auth, $location, Post, UserData) {
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
              $scope.alert = {'message':data.errorType, 'type':'danger'}
            }
          });
        }
      });
    })

    var setUser = function(user) {
      $scope.user = user;
      UserData.setUser(user);
    }

    $scope.$watch(function() { return UserData.getUser() }, function(newValue) {
      $scope.user = newValue;
    }, true)

    getUser(UserData, $http, $auth, function(user) {
      setUser(user);
    })

    var planHtml = '/static/partials/plan.html';
    $scope.plans = [
      {
        url:planHtml,
        selection:'monthly', getTerm:'Purchase',
        description:'Monthly Subscription', price:500,
        isSubscription:true, period:'month',
        title:"Monthly Service",
        details:[
          "Two lattes at Sightglass.",
          "Or focus and deeper thought.",
          "Our Top Choice."
        ]
      },
      // {
      //   url:planHtml,
      //   selection:'break',
      //   description:'Email Break', price:500,
      //   title:"Take a break. Recharge.",
      //   details:[
      //     "Are you on vacation?",
      //     "Treat yourself.",
      //     "A fine beer at Monk's Kettle.",
      //     "Or an opportunity to let go."
      //   ]
      // },
      {
        url:planHtml,
        selection:'trial', getTerm:'Start',
        description:'One Week Trial', price:0,
        title:"One Week Red Pill",
        details:[
          "Free trial.",
          "Come on board.",
          "The water's warm."
        ]
      }
    ]

    $scope.buy = function(plan) {
      $scope.closeAlert();
      if (plan.selection == 'trial') {
        Post.postTrial($scope.user.customer_id).then(function(response) {
          var data = response.data;
          if (data.success) {
            setUser(data.user);
            $location.path('/me');
          } else {
            $scope.alert = {'message':'Error activating the trial.', 'type':'danger'}
          }
        });
      } else {
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
          UserData.setUser($scope.user)
          $location.path('/plans')
        }
      })
    }
  })
  .controller('profile', function($scope, $http, Post, $timeout, $auth, $location, UserData) {
    $scope.clock = Date.now()
    $scope.tickInterval = 1000
    var tick = function() {
      $scope.clock = Date.now()
      $timeout(tick, $scope.tickInterval);
    }
    $timeout(tick, $scope.tickInterval);

    $scope.activateButtonDescription = function() {
      if ($scope.user.isArchiving) {
        return "Archiving ..."
      } else {
        return "Start Service"
      }
    }

    $scope.$watch(function() { return UserData.getUser() }, function(newValue) {
      if (newValue && !newValue.timeblocks) {
        getTimeInfo(newValue)
      } else if (newValue) {
        $scope.user = newValue;
      }
    }, true)

    var getTimeInfo = function(user) {
      if (user) {
        setTimeInfo(user);
      } else {
        getUser(UserData, $http, $auth, function(user) {
          if (!user) {
            $location.path('/')
          } else {
            setTimeInfo(user);
          }
        })
      }
    }
    getTimeInfo($scope.user)

    var setTimeInfo = function(user) {
      $http.get('/get-time-info/' + user.customer_id).then(function(response) {
        var data = response.data;
        if (data.success) {
          setUser(data.user);
        }
      })
    }

    $scope.allInboxes = null;
    $scope.currTimeblocks = [];
    var setUser = function(user) {
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

      $scope.currTimeblocks = [];
      user.timeblocks.forEach(function(block) {
        $scope.currTimeblocks.push(block);
      })
    }

    $scope.setTimezone = function() {
      var tzOffset = getTzOffset();
      Post.postTimezone($scope.user.customer_id, tzOffset).then(function(response) {
        var data = response.data;
        if (data.success) {
          setUser(data.user);
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
      } else if (!$scope.user.isActive || !$scope.user.isArchived) {
        return true;
      } else {
        return isInValidTimeRange($scope.user.lastTbAdj) && isBlocksDifferent();
      }
    }
    $scope.canSubmitTimeblocks = function() {
      if (!$scope.user) {
        return false;
      } else {
        return isBlocksDifferent();
      }
    }

    var isInValidTimeRange = function(time) {
      return !time || time < new Date(new Date() - 1000*60*60*24*3)
    }

    var isBlocksDifferent = function() {
      var currTimeblocks = $scope.currTimeblocks.map(function(block) { return block.start }).sort()
      var adjTimeblocks  = $scope.user.timeblocks.map(function(block) { return block.start }).sort()
      return !currTimeblocks.equals(adjTimeblocks)
    }

    $scope.getBlockDescription = function(block) {
      if ($scope.canSetTimeblocks()) {
        return 'Select to change period ' + ($scope.user.timeblocks.indexOf(block) + 1) + ':'
      } else {
        return 'Period start time:'
      }
    }

    $scope.toggleBlock = function(block) {
      var index = $scope.user.timeblocks.map(function(userBlock) { return userBlock.start }).indexOf(block.num);
      if (index > -1) {
        $scope.user.timeblocks.splice(index, 1);
      } else {
        $scope.user.timeblocks.push({'start':block.num, 'length':60});
      }
    }

    $scope.activateAccount = function() {
      Post.postActivate($scope.user.customer_id).then(function(response) {
        var data = response.data;
        if (data.success) {
          setUser(data.user);
        }
      })
    }

    $scope.updateTimeblocks = function() {
      Post.postBlocks($scope.user.customer_id, $scope.user.timeblocks).then(function(response) {
        var data = response.data;
        if (data.success) {
          setUser(data.user);
        }
      })
    }

    $scope.calendarColumns = [allBlockChoices.slice(0,6), allBlockChoices.slice(6,12), allBlockChoices.slice(12,18), allBlockChoices.slice(18,24)]
    $scope.isUserBlock = function(calendarBlock) {
      if (!$scope.user) {
        return false;
      }
      return $scope.user.timeblocks.some(function(block) {
        return calendarBlock.num == block.start
      })
    }

  })
  .controller('faq', function($scope) {
    $scope.faq = [
      {'question':"What if I don't like the time periods I choose?",
       'answer':"Change them. You can do this once every 24 hours."},
      {'question':"What happens when I'm in a new timezone?",
       'answer':"Visit your profile and there will be an option to adjust it."},
      {'question':"What email clients do you support?",
       'answer':"Only Gmail at the moment."},
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
  var userDataUser = userData.getUser();
  if (userDataUser) {
    return userDataUser;
  }

  var userToken = auth.getToken()
  if (userToken) {
    http.get('/user-from-token/' + userToken).then(function(response) {
      var data = response.data;
      if (data.success) {
        if (data.user) {
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

var allHours = [12].concat(Array.apply(null, Array(11)).map(function (_, i) { return i+1 }));
var allTimes = allHours.map(function(hour) {
  var ret = {'strHour':hour.toString() + ' am', 'numHour':hour*60}
  if (hour == 12) {
    ret['numHour'] = 0;
  }
  return ret;
}).concat(
  allHours.map(function(hour) {
    var ret = {'strHour':hour.toString() + ' pm', 'numHour':hour*60}
    if (hour < 12) {
      ret['numHour'] += 12*60;
    }
    return ret
  })
);
var allBlockChoices = allTimes.map(function(time, index) {
  if (index == 23) {
    return {'start':time.strHour, 'end':allTimes[0].strHour, 'num':time.numHour}
  } else {
    return {'start':time.strHour, 'end':allTimes[index+1].strHour, 'num':time.numHour}
  }
})

window.mobilecheck = function() {
  var check = false;
  (function(a){if(/(android|bb\d+|meego).+mobile|avantgo|bada\/|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|mobile.+firefox|netfront|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|series(4|6)0|symbian|treo|up\.(browser|link)|vodafone|wap|windows (ce|phone)|xda|xiino/i.test(a)||/1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\-(n|u)|c55\/|capi|ccwa|cdm\-|cell|chtm|cldc|cmd\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\-s|devi|dica|dmob|do(c|p)o|ds(12|\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\-|_)|g1 u|g560|gene|gf\-5|g\-mo|go(\.w|od)|gr(ad|un)|haie|hcit|hd\-(m|p|t)|hei\-|hi(pt|ta)|hp( i|ip)|hs\-c|ht(c(\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\-(20|go|ma)|i230|iac( |\-|\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\/)|klon|kpt |kwc\-|kyo(c|k)|le(no|xi)|lg( g|\/(k|l|u)|50|54|\-[a-w])|libw|lynx|m1\-w|m3ga|m50\/|ma(te|ui|xo)|mc(01|21|ca)|m\-cr|me(rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\-2|po(ck|rt|se)|prox|psio|pt\-g|qa\-a|qc(07|12|21|32|60|\-[2-7]|i\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\-|oo|p\-)|sdk\/|se(c(\-|0|1)|47|mc|nd|ri)|sgh\-|shar|sie(\-|m)|sk\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\-|v\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\-|tdg\-|tel(i|m)|tim\-|t\-mo|to(pl|sh)|ts(70|m\-|m3|m5)|tx\-9|up(\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|yas\-|your|zeto|zte\-/i.test(a.substr(0,4)))check = true})(navigator.userAgent||navigator.vendor||window.opera);
  return check;
}

Array.prototype.equals = function (array) {
    // if the other array is a falsy value, return
    if (!array)
        return false;

    // compare lengths - can save a lot of time
    if (this.length != array.length)
        return false;

    for (var i = 0, l=this.length; i < l; i++) {
        // Check if we have nested arrays
        if (this[i] instanceof Array && array[i] instanceof Array) {
            // recurse into the nested arrays
            if (!this[i].equals(array[i]))
                return false;
        }
        else if (this[i] != array[i]) {
            // Warning - two different object instances will never be equal: {x:20} != {x:20}
            return false;
        }
    }
    return true;
}