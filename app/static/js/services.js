'use strict';

angular.module('hidemailServices', ['ngRoute', 'ngResource'])
  .factory('Post', function($http) {
    return {
      postOauth: function() {
        return $http.post('/login/google', {
          headers: {'Content-Type': undefined},
          transformRequest: angular.identity
        });
      },
      postBlocks: function(blocks) {
        return $http.post('/update-blocks', {
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          data: blocks
        })
      },
      postTimezone: function(tz) {
        return $http.post('/update-timezone', {
          headers: {'Content-Type': 'application/x-www-form-urlencoded'},
          data: tz
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
  });
