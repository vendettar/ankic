// Simple audio controls wiring. Looks for elements with data-audio-target
// and plays the matching <audio id="..."> when clicked.
(function () {
  function onReady(fn) {
    if (document.readyState === 'complete' || document.readyState === 'interactive') {
      setTimeout(fn, 0);
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
  }

  function playById(id) {
    if (!id) return;
    var audio = document.getElementById(id);
    if (!audio) {
      return;
    }
    // Pause other audios first
    try {
      var all = document.querySelectorAll('audio');
      for (var i = 0; i < all.length; i++) {
        if (all[i] !== audio && typeof all[i].pause === 'function') {
          all[i].pause();
        }
      }
    } catch (_) {}

    try { audio.currentTime = 0; } catch (_) {}
    if (typeof audio.play === 'function') {
      audio.play();
    }
  }

  onReady(function () {
    // Event delegation for clicks
    document.addEventListener('click', function (e) {
      var target = e.target;
      if (!target) return;

      var el = target.closest ? target.closest('[data-audio-target]') :
               (function() {
                 while (target && target !== document) {
                   if (target.getAttribute && target.getAttribute('data-audio-target')) {
                     return target;
                   }
                   target = target.parentNode;
                 }
                 return null;
               })();

      if (!el) return;
      var id = el.getAttribute('data-audio-target');
      playById(id);
    });

    // Keyboard support (Enter/Space)
    document.addEventListener('keydown', function (e) {
      var target = e.target;
      if (!target) return;

      var hasDataAttr = target.getAttribute && target.getAttribute('data-audio-target');
      if (!hasDataAttr) return;

      var key = e.key || e.code;
      if (key === 'Enter' || key === ' ' || key === 'Spacebar') {
        e.preventDefault();
        var id = target.getAttribute('data-audio-target');
        playById(id);
      }
    });
  });
})();
