'use strict';

var lsKey = 'BatchMail-user';

angular.module('HideMail', ['hidemailServices', 'hidemailDirectives', 'angular-loading-bar', 'satellizer'])
  .controller('main', function($scope, $http, $auth, LocalStorage) {
    $scope.getUser = function(callback) {
      var isSupported = LocalStorage.isSupported()
      if (!isSupported || !LocalStorage.get(lsKey)) {
        var userToken = $auth.getToken()
        if (userToken) {
          $http.get('/api/user-from-token/' + userToken).then(function(response) {
            var data = response.data;
            if (data.success == true) {
              if (data.user) {
                callback(data.user);
                LocalStorage.set(lsKey, data.user);
              } else if (data.token == false) {
                $auth.logout()
              }
            }
          })
        }
      } else if (isSupported) {
        var user = LocalStorage.get(lsKey)
        if (user) {
          callback(user);
        }
      }
    }
  })
  .controller('about', function($scope) {

  })
  .controller('home', function($scope, $auth, Post, LocalStorage) {
    if (!$scope.user) {
      $scope.$parent.getUser(function(user) {
        $scope.user = user;
      })
    }

    $scope.logout = function() {
      $scope.user = null;
      LocalStorage.remove(lsKey);
      $auth.logout();
    }

    $scope.oauth = function() {
      $auth.authenticate('google', {'state':{'tzOffset':new Date().getTimezoneOffset()}}).then(function(response) {
        if (response.data.success) {
          $scope.user = response.data.user;
          LocalStorage.set(lsKey, $scope.user)
        } else {
          console.log('failed to authenticate.');
        }
      })
    }
  })
  .controller('profile', function($scope) {
    /*
       Get the timeblock info for the user and put it in here.
       Load up a time adjuster.
    */
  })
  .controller('timeblocks', function($scope, $http, Post, $timeout) {
    $scope.$parent.getUser(function(user) {
      if (!user) {
        $location.path('/')
      } else {
        $scope.user = user;
        $http.get('/api/get-time-info/' + user.email).then(function(response) {
          var data = response.data;
          if (data.success) {
            setUser(data.user);
          } else {
            console.log('oops, coulnt get the users time info')
          }
        })
      }
    })

    var setUser = function(user) {
      $scope.user = user;
      if ($scope.user.lastTzAdj) {
        $scope.user.lastTzAdj = new Date($scope.user.lastTzAdj)
      }
      if ($scope.user.lastTbAdj) {
        $scope.user.lastTbAdj = new Date($scope.user.lastTbAdj)
      }
      setBlocks($scope.user)
    }

    var setBlocks = function(user) {
      $scope.blocks = user.timeblocks.map(function(block) {
        var period = 'PM'
        var length = block.length
        var hour = parseInt(block.start)/60
        if (hour < 12) {
          period = 'AM'
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
      var tzOffset = (new Date()).getTimezoneOffset()
      Post.postTimezone($scope.user.email, tzOffset).then(function(response) {
        var data = response.data;
        if (data.success) {
          setUser(data.user);
        } else {
          console.log('failure in posting timezone');
        }
      })
    }

    $scope.getSetTimezoneDesc = function() {
      if ($scope.canSetTimezone()) {
        return "Set to current timezone:";
      } else {
        return "Timezone currently set to:";
      }
    }
    $scope.canSetTimezone = function() { //This gets called every single time the clock ticks
      return canSetTimeHelper($scope.user.lastTzAdj, $scope.user.currTzOffset);
    }
    $scope.canSetTimeblocks = function() {
      return true;
//       return canSetTimeHelper($scope.user.lastTbAdj);
    }
    var canSetTimeHelper = function(time, offset) {
      var now = new Date();
      if (!time) {
        return true;
      } else if (offset && offset == now.getTimezoneOffset()) {
        return false;
      } else {
        return is_out_of_range(time, new Date(time - 1000*60*60*24*2), new Date(now - 1000*60*15))
      }
    }
    var is_out_of_range = function(time, beg, end) {
      return time < beg || time > end
    }

    $scope.tickInterval = 1000
    var tick = function() {
      $scope.clock = Date.now()
      $timeout(tick, $scope.tickInterval);
    }
    $timeout(tick, $scope.tickInterval);

    $scope.getBlockDescription = function(block) {
      return numToWords(block.length.toString()) + ' Minute Block: '
    }

    $scope.getAvailableTimes = function(blockTime) {
      var ret = allTimes.filter(function(time) { return $scope.times.indexOf(time) == -1 })
      ret.unshift(blockTime);
      return ret;
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

      Post.postBlocks($scope.user.email, timeblocks).then(function(response) {
        var data = response.data;
        if (data.success) {
          setUser(data.user);
        } else {
          console.log('failure in posting blocks');
        }
      })
    }
  })
  .config([
    '$routeProvider', '$locationProvider', '$authProvider',
    function($routeProvider, $locationProvider, $authProvider) {
      $routeProvider
	.when('/', {
	  templateUrl: '/static/partials/home.html',
          controller: 'home'
	})
        .when('/login', {
          templateUrl: '/static/partials/login.html',
          controller: 'login'
        })
        .when('/signup', {
          templateUrl: '/static/partials/signup.html',
          controller: 'signup'
        })
        .when('/about', {
          templateUrl: '/static/partials/about.html',
          controller: 'about'
        })
        .when('/me', {
          templateUrl: '/static/partials/profile.html',
          controller: 'profile',
          resolve: {
            authenticated: function($location, $auth) {
              if (!$auth.isAuthenticated()) {
                return $location.path('/');
              }
            }
          }
        })
        .when('/timeblocks', {
          templateUrl: '/static/partials/timeblocks.html',
          controller: 'timeblocks'
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

function redirectIfNotArgs(params, $location) {
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

var allHours = [12].concat(Array.apply(null, Array(11)).map(function (_, i) { return i+1 }))
var allTimes = allHours.map(function(hour) { return hour.toString() + ' AM' }).concat(allHours.map(function(hour) { return hour.toString() + ' PM' }))

window.mobilecheck = function() {
  var check = false;
  (function(a){if(/(android|bb\d+|meego).+mobile|avantgo|bada\/|blackberry|blazer|compal|elaine|fennec|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|mobile.+firefox|netfront|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|series(4|6)0|symbian|treo|up\.(browser|link)|vodafone|wap|windows (ce|phone)|xda|xiino/i.test(a)||/1207|6310|6590|3gso|4thp|50[1-6]i|770s|802s|a wa|abac|ac(er|oo|s\-)|ai(ko|rn)|al(av|ca|co)|amoi|an(ex|ny|yw)|aptu|ar(ch|go)|as(te|us)|attw|au(di|\-m|r |s )|avan|be(ck|ll|nq)|bi(lb|rd)|bl(ac|az)|br(e|v)w|bumb|bw\-(n|u)|c55\/|capi|ccwa|cdm\-|cell|chtm|cldc|cmd\-|co(mp|nd)|craw|da(it|ll|ng)|dbte|dc\-s|devi|dica|dmob|do(c|p)o|ds(12|\-d)|el(49|ai)|em(l2|ul)|er(ic|k0)|esl8|ez([4-7]0|os|wa|ze)|fetc|fly(\-|_)|g1 u|g560|gene|gf\-5|g\-mo|go(\.w|od)|gr(ad|un)|haie|hcit|hd\-(m|p|t)|hei\-|hi(pt|ta)|hp( i|ip)|hs\-c|ht(c(\-| |_|a|g|p|s|t)|tp)|hu(aw|tc)|i\-(20|go|ma)|i230|iac( |\-|\/)|ibro|idea|ig01|ikom|im1k|inno|ipaq|iris|ja(t|v)a|jbro|jemu|jigs|kddi|keji|kgt( |\/)|klon|kpt |kwc\-|kyo(c|k)|le(no|xi)|lg( g|\/(k|l|u)|50|54|\-[a-w])|libw|lynx|m1\-w|m3ga|m50\/|ma(te|ui|xo)|mc(01|21|ca)|m\-cr|me(rc|ri)|mi(o8|oa|ts)|mmef|mo(01|02|bi|de|do|t(\-| |o|v)|zz)|mt(50|p1|v )|mwbp|mywa|n10[0-2]|n20[2-3]|n30(0|2)|n50(0|2|5)|n7(0(0|1)|10)|ne((c|m)\-|on|tf|wf|wg|wt)|nok(6|i)|nzph|o2im|op(ti|wv)|oran|owg1|p800|pan(a|d|t)|pdxg|pg(13|\-([1-8]|c))|phil|pire|pl(ay|uc)|pn\-2|po(ck|rt|se)|prox|psio|pt\-g|qa\-a|qc(07|12|21|32|60|\-[2-7]|i\-)|qtek|r380|r600|raks|rim9|ro(ve|zo)|s55\/|sa(ge|ma|mm|ms|ny|va)|sc(01|h\-|oo|p\-)|sdk\/|se(c(\-|0|1)|47|mc|nd|ri)|sgh\-|shar|sie(\-|m)|sk\-0|sl(45|id)|sm(al|ar|b3|it|t5)|so(ft|ny)|sp(01|h\-|v\-|v )|sy(01|mb)|t2(18|50)|t6(00|10|18)|ta(gt|lk)|tcl\-|tdg\-|tel(i|m)|tim\-|t\-mo|to(pl|sh)|ts(70|m\-|m3|m5)|tx\-9|up(\.b|g1|si)|utst|v400|v750|veri|vi(rg|te)|vk(40|5[0-3]|\-v)|vm40|voda|vulc|vx(52|53|60|61|70|80|81|83|85|98)|w3c(\-| )|webc|whit|wi(g |nc|nw)|wmlb|wonu|x700|yas\-|your|zeto|zte\-/i.test(a.substr(0,4)))check = true})(navigator.userAgent||navigator.vendor||window.opera);
  return check;
}