
(function() {

    var socket = io.connect('/plamp');

    var pushme_button = document.querySelector("#pushme")
    pushme_button.onclick = function() {
	
	var r = 0
        var g = 0
        var b = 0
        for (var i=0; i < 100; i++)
	{
	    r += 13
	    b += 1
            g += 3
	
	    if (r > 255) r = 0
	    if (g > 255) g = 0
	    if (b > 255) b = 0
            socket.emit('color_wipe', '['+r+','+g+','+b+',0]')
        }
    }
    var r_range = document.getElementById('r_id')
    var g_range = document.getElementById('g_id')
    var b_range = document.getElementById('b_id')
    r_range.onchange = slider_wipe
    b_range.onchange = slider_wipe
    g_range.onchange = slider_wipe

    function slider_wipe() {
       var r = r_range.value
       var g = g_range.value
       var b = b_range.value
       socket.emit('color_wipe', '['+r+','+g+','+b+',0]')
    }
})();
