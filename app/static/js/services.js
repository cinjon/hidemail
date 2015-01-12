'use strict';

angular.module('hidemailServices', ['ngRoute', 'ngResource', 'LocalStorageModule'])
  .factory('Post', function($http) {
    return {
      postBlocks: function(customer_id, blocks) {
        return $http.post('/update-blocks', {
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          data: {'timeblocks':blocks, 'customer_id':customer_id}
        })
      },
      postTimezone: function(customer_id, tzOffset) {
        return $http.post('/update-timezone', {
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          data: {'tz':tzOffset, 'customer_id':customer_id}
        })
      },
      postPayment: function(token) {
        return $http.post('/post-payment', {
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          data: {'token':token}
        })
      },
      postTrial: function(customer_id) {
        return $http.post('/post-trial', {
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
