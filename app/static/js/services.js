'use strict';

angular.module('hidemailServices', ['ngRoute', 'ngResource'])
  .factory('Post', function($http) {
    return {
      doSomething: function(form) {
        return $http.post('/do-something', form, {
          headers: {'Content-Type': undefined},
          transformRequest: angular.identity
        });
      }
    }
  });
