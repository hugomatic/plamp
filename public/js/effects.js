
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
})();
