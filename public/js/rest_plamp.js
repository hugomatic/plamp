function post_data(route, data, response_div)
{
    var host = document.getElementById("host_id" ).value
    var xmlhttp = xmlhttp=new XMLHttpRequest();
    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState==4 && xmlhttp.status >= 200 && xmlhttp.status < 300) {
            var div = document.getElementById(response_div)
	    var s = xmlhttp.responseText +'<br>' + div.innerHTML
            div.innerHTML = s
        }
    }
    var url = host + route;
    console.log('posting to '  + url)
    xmlhttp.open("POST", url, true)
    xmlhttp.setRequestHeader("Content-Type","application/json")
    var s = JSON.stringify(data)
    xmlhttp.send(s)
  
}

function send_color_wipe()
{   
    var data  = JSON.parse(document.getElementById("colorwipe_id" ).value);
    console.log('color wipe ' + data);
    post_data("/color_wipe", data, "responseDiv");
    console.log('done')
}

function send_color_array()
{
    var s = document.getElementById("array_values_id").value
    var data = JSON.parse(s)
    console.log('send_color_array')
    post_data("/color_array", data, "responseDiv");
    console.log('done')
}

