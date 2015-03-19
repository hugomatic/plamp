(function() {

    var socket = io.connect('/plamp');

    var $color_wipe_form = $('#color_wipe');
    $color_wipe_form.bind('submit', function() {
        var $input = $(this).find('input');
        var s = $input.val();
        socket.emit('color_wipe', s);
        $input.val('');
        return false;
    });

    var $color_array_form = $('#color_array');
    $color_array_form.bind('submit', function() {
        var $input = $(this).find('input');
        var s = $input.val();
        socket.emit('color_array', s);
        $input.val('');
        return false;
    });

    var $status = $('#status');
    var $status_wipe = $('#status_wipe');
    var $status_array = $('#status_array');

    socket.on('connect', function() {
        $status.html('<b>Connected: ' + socket.socket.transport.name + '</b>');
    });
    socket.on('error', function() {
        $status.html('<b>Error</b>');
    });
    socket.on('disconnect', function() {
        $status.html('<b>Closed</b>');
    });

   socket.on('color_wiped', function(msg) {
        $status_wipe.html('<b>color_wiped</b> ' + JSON.stringify(msg));
    });

   socket.on('color_arrayed', function(msg) {
        $status_array.html('<b>color_arrayed</b> ' + JSON.stringify(msg));
    });

})();
