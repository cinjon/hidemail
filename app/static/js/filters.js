angular.module('hidemailFilters', [])
  .filter('lowercase', function() {
    return function(input) {
      if (input) {
        return input.toLowerCase();
      }
    }
  });
