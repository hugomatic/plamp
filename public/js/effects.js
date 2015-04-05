
(function() {

    var socket = io.connect('/plamp');

    var button_pushme = document.querySelector("#button_pushme")
    var button_off = document.querySelector("#button_off")

    document.querySelector("#button_red").onclick = function() { socket.emit('color_wipe', '[255,0,0,0]') }    
    document.querySelector("#button_green").onclick = function() { socket.emit('color_wipe', '[0,255,0,0]') }    
    document.querySelector("#button_blue").onclick = function() { socket.emit('color_wipe', '[0,0,255,0]') }    
    document.querySelector("#button_yellow").onclick = function() { socket.emit('color_wipe', '[255,200,0,0]') }    
    document.querySelector("#button_white").onclick = function() { socket.emit('color_wipe', '[10,10,10,0]') }    
    document.querySelector("#button_off").onclick = function() { socket.emit('color_wipe', '[0,0,0,0]') }    
	
    button_pushme.onclick = function() {
	
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
