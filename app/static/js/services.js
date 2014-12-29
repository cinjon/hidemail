'use strict';

angular.module('hidemailServices', ['ngRoute', 'ngResource', 'LocalStorageModule'])
  .factory('Post', function($http) {
    return {
      postBlocks: function(email, blocks) {
        return $http.post('/update-blocks', {
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          data: {'timeblocks':blocks, 'email':email}
        })
      },
      postTimezone: function(email, tzOffset) {
        return $http.post('/update-timezone', {
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          data: {'tz':tzOffset, 'email':email}
        })
      },
      postPayment: function(token) {
        return $http.post('/post-payment', {
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          data: {'token':token}
        })
      }
    }
  })
  .factory('Get', function($http) {
    return {
      getUserFromToken: function(token) {
        return $http.get('/api/user-from-token/' % token)
      }
    }
  })
  .factory('UserData', function() {
    var userData = null;
    function setUser(data) {
      userData = data;
    }
    function getUser() {
      return userData;
    }

    return {
      getUser: getUser,
      setUser: setUser
    }
  })
  .factory('LocalStorage', function(localStorageService) {
    return {
      get: function(key) {
        return localStorageService.get(key)
      },
      set: function(key, value) {
        localStorageService.set(key, value);
      },
      isSupported: function() {
        return localStorageService.isSupported;
      },
      remove: function(key) {
        return localStorageService.remove(key);
      }
    }
  })
