$(function(){
    var canvas = $('#tools_sketch')[0];
    var ctx = canvas.getContext('2d');
    var width = canvas.width;
    var height = canvas.height;

    // const default_alpha_int = 120;
    // const default_global_alpha = default_alpha_int/255;
    const default_global_comp_op = 'source-over';

    var active_color_r = Number($("#active_color_r").attr("value"));
    var active_color_g = Number($("#active_color_g").attr("value"));
    var active_color_b = Number($("#active_color_b").attr("value"));
    var default_active_color = "rgb(" + String(active_color_r) + "," + String(active_color_g) + "," + String(active_color_b) + ")";
    var active_color = default_active_color;

    // Get pencil stroke size
    var pen_slider = document.getElementById("pencil_size_bar");
    var pen_output = document.getElementById("pencil_size_label");

    var pencil_size = pen_slider.value;
    pen_output.innerHTML = pen_slider.value;

    pen_slider.oninput = function() {
      pencil_size = this.value;
      pen_output.innerHTML = this.value;
    }

    // Get opacity
    var opa_slider = document.getElementById("opacity_label_bar");
    var opa_output = document.getElementById("opacity_label");

    var opacity = opa_slider.value;
    var global_alpha = opacity/255;
    ctx.globalAlpha = global_alpha;

    opa_output.innerHTML = global_alpha.toPrecision(2);

    opa_slider.oninput = function() {
      opacity = this.value;
      global_alpha = opacity/255;
      ctx.globalAlpha = global_alpha;
      opa_output.innerHTML = global_alpha.toPrecision(2);

      var prev_ctx = ctx.globalCompositeOperation;

      ctx.globalCompositeOperation = "source-over";
      image_wo_alpha = change_alpha(opacity);
      ctx.putImageData(image_wo_alpha, 0, 0);

      ctx.globalCompositeOperation = prev_ctx;
    }

    // global composition operation
    ctx.globalCompositeOperation = default_global_comp_op;
    
    // initial cursor style
    document.getElementById('tools_sketch').style.cursor = "crosshair";

    // temporary image data stack
    var tempimgData = [];

    // temporary mask button event stack
    var maskbutData = [];
    var deactallflagData = [];

    // Undo button
    $("#undo_btn").on("click", function(){
        ctx.putImageData(tempimgData.pop(),0,0);
        if (tempimgData.length==0) {
            document.getElementById('undo_btn').disabled = true
        }
        var mask_butt_elelist = maskbutData.pop();
        var deactallflag = deactallflagData.pop();

        if ( deactallflag == true ) {
            for ( mask_butt_ele of mask_butt_elelist ) {
                mask_butt_ele.classList.add("active")
            }
        } else if ( mask_butt_elelist.length == 1 ) {
            if (mask_butt_elelist[0].hasClass("active")) {
                mask_butt_elelist[0].removeClass("active")
            } else {
                mask_butt_elelist[0].addClass("active")
            }
        }
    })

    // Damage site predicted by heatmap on click
    $(".maskswitch").on("click", function(){
        if ( $(this).hasClass("active")) {
            update_undo_stack([$(this)])
            var img = document.getElementById($(this).attr("maskid"));
            ctx.globalAlpha = 1;
            var prev_ctx = ctx.globalCompositeOperation;

            ctx.globalCompositeOperation = "destination-out";
            ctx.drawImage(img, 0, 0, width, height);
            ctx.globalCompositeOperation = prev_ctx;

            ctx.globalAlpha = global_alpha;
            $(this).removeClass("active");
        } else {
            update_undo_stack([$(this)])
            var img = document.getElementById($(this).attr("maskid"));
            var prev_ctx = ctx.globalCompositeOperation;
            ctx.globalCompositeOperation = "source-over";
            ctx.drawImage(img, 0, 0, width, height);
            ctx.globalCompositeOperation = prev_ctx;
            $(this).addClass("active");
        }
    })

    // clear button
    $("#clearbutton").on("click", function(){
        update_undo_stack($("a.active[id^=togglemask_]"), true);
        ctx.clearRect(0, 0, width, height);
        $("[id^=togglemask_]").removeClass("active");
    })

    // Add annotation button
    $("#addannotation").on("click", function(){
        var curr_cntr = Number($(this).attr("value"));
        var newid = curr_cntr + 1; 
        var dmgtypes = $("#dmgtypes").attr("value");
        var dmgtypes_selection = "";
        var active_id = $("button.active[id^=annotation_trigger_]").attr("value");

        // deactivate all other annotation_trigger button
        $("[id^=annotation_trigger_]").removeClass("active");

        // prepare selection options
        for ( x of JSON.parse(dmgtypes.replace(/'/g, '"')) ) {
            dmgtypes_selection += '<option value="TYPE" selected="" id="dmg_type_site_COUNTER_TYPE">TYPE</option>'.replace(
                /TYPE/g, String(x)
            )
        }

        // deactive all previous delete button
        $("[id^=delete_site_]").attr("disabled", "true");

        // append the whole html
        $("#todlabelpanel").append(`
          <div class="input-group mb-3">
            <button type="button" class="btn btn-outline-warning active" id="annotation_trigger_COUNTER" value="COUNTER" style="margin-right: 30px;width:80px;border-radius:10px" onclick="trigger_annotation(this)">Site COUNTER</button>
            <div class="input-group-prepend">
              <label class="input-group-text">Damage Type</label>
            </div>
            <select class="custom-select" name="dmg_type_site_COUNTER">
            DMGTYPEOPTIONS
            </select>
            <button type="button" id="delete_site_COUNTER" class="btn btn-danger" onclick="deletelabel(this)" style="margin-left: 30px;color:white;border-radius: 10px">Delete</button>
            <img id="annotation_site_COUNTER_img" src="" style="display: none"> 
            <input type="hidden" name="annotation_site_COUNTER" id="annotation_site_COUNTER">
          </div>
        `.replace(/COUNTER/g, String(newid)).replace(
            /DMGTYPEOPTIONS/g,
            dmgtypes_selection
        ));

        // update counter
        document.getElementById("addannotation").value = newid;

        // save old annotation
        save_annotation(active_id);

        // reset canvas
        reset_canvas()

        // save blank for new annotation
        save_annotation(newid);
    });



    // Eraser tool 
    $('#erasertool').on("click", function(){
        var erasertool = document.getElementById('erasertool');
        if ( erasertool.innerHTML == "Switch to Eraser Mode" ) {
            active_color = "rgba(0,0,0,1)";
            ctx.globalCompositeOperation = "destination-out";
            document.getElementById('tools_sketch').style.cursor = "url('/static/erasercursor.cur'), auto";
            document.getElementById('fillregion').innerHTML = "Fill (off)";
            document.getElementById('fillregion').className = "btn btn-outline-danger";
            document.getElementById('erasertool').innerHTML = "Switch to Pencil Mode";
        } else {
            active_color = default_active_color;
            ctx.globalCompositeOperation = default_global_comp_op;
            $("#fillregion")[0].disabled = false;
            document.getElementById('tools_sketch').style.cursor = "crosshair";
            document.getElementById('erasertool').innerHTML = "Switch to Eraser Mode";
        }
    })

    // Fill tool (won't activate under eraser mode)
    $('#fillregion').on("click", function(){
        var fill_switch = document.getElementById('fillregion').innerHTML;
        var erasertool_state = document.getElementById('erasertool').innerHTML;
        if ( fill_switch == "Fill (on)" ) {
            document.getElementById('fillregion').innerHTML = "Fill (off)";
            document.getElementById('fillregion').className = "btn btn-outline-danger";
            document.getElementById('tools_sketch').style.cursor = "crosshair";
        } else {
            if (erasertool_state == "Switch to Eraser Mode") {
                document.getElementById('fillregion').innerHTML = "Fill (on)";
                document.getElementById('fillregion').className = "btn btn-danger";
                document.getElementById('tools_sketch').style.cursor = "url('/static/paintcursor.cur'), auto";
            }
        }
    })

    // function to change alpha
    function change_alpha(alpha_value_int) {
        // buffer number of alpha
        const alpha_buffer = 20;

        // get the image data object
        var image = ctx.getImageData(0, 0, width, height);

        // get the image data values 
        var imageData = image.data;

        // set every fourth value to preset value
        for (var i=3; i < imageData.length; i+=4) {  
            if ( (imageData[i-3] > 0 || imageData[i-2] > 0 || imageData[i-1] > 0) && ( imageData[i] > alpha_buffer) ) {
                imageData[i] = alpha_value_int;
            } else if  ( (imageData[i-3] > 0 || imageData[i-2] > 0 || imageData[i-1] > 0) && ( imageData[i] < alpha_buffer) ) {
                imageData[i-3] = 0;
                imageData[i-2] = 0;
                imageData[i-1] = 0
                imageData[i] = 0;
            }
        };

        // after the manipulation, reset the data
        image.data = imageData;


        return image
    }


    // function to update temporary data stack
    function update_undo_stack(maskbut=[], forceflag=false){
        tempimgData.push(ctx.getImageData(0,0,width,height));
        maskbutData.push(maskbut);
        deactallflagData.push(forceflag);
        document.getElementById('undo_btn').disabled = false
    }

    // function to save canvas current drawings
    function save_annotation(id) {
        var prev_ctx = ctx.globalCompositeOperation;

        ctx.globalCompositeOperation = "source-over";
        image_wo_alpha = change_alpha(255);
        ctx.putImageData(image_wo_alpha, 0, 0);

        ctx.globalCompositeOperation = prev_ctx;

        $('input[name="annotation_site_' + String(id) + '"]').val(canvas.toDataURL('png'));
        var img_ = document.getElementById("annotation_site_" + String(id) + "_img");
        img_.src = canvas.toDataURL('png');
    }

    // function to reset canvas
    function reset_canvas() {
        tempimgData = [];
        maskbutData = [];
        deactallflagData = [];
        ctx.clearRect(0, 0, width, height);
        $("[id^=togglemask_]").removeClass("active");
        document.getElementById('undo_btn').disabled = true;
    }

    // Pencil mode to draw line on the background
    var pencil = new Pencil();

    function Pencil(){
        var tool = this;
        this.started = false;
        this.touchstart = this.mousedown = function(event) {
            update_undo_stack()
            ctx.beginPath();
            ctx.moveTo(event.offsetX, event.offsetY);
            tool.started = true;
        };

        this.touchmove = this.mousemove = function(event){
            if (tool.started){
                ctx.lineWidth = pencil_size;
                ctx.strokeStyle = active_color;
                ctx.lineTo(event.offsetX, event.offsetY);
                ctx.stroke();
            }
        };

        this.touchend = this.mouseup = function(event){
            if (tool.started){
                tool.mousemove(event);
                tool.started = false;
            }
        }

        $(canvas).on("mouseleave", function(){
            tool.started = false;
        })

        $(canvas).on("mouseout", function(){
            tool.started = false;
        })


    }

    // Painter mode to fill a region
    var painter = new Painter();
    function Painter(){

        this.paint = function(event){
        update_undo_stack()
        var dx = [ 0, -1, +1,  0];
        var dy = [-1,  0,  0, +1];


        var imgDatad = ctx.getImageData(0,0,width,height);

        var stack = [];
        stack.push([event.offsetX, event.offsetY]);

        while (stack.length > 0){
            var curPoint = stack.pop();
            var curX = curPoint[0];
            var curY = curPoint[1];

            for (var i=0;i<4;i++){
                var nextX = curX + dx[i];
                var nextY = curY + dy[i];

                if (nextX<0 || nextY <0 || nextX>=width || nextY>=height){
                    continue;
                }

                var nextpoint = (nextY*width + nextX) * 4;

                if (imgDatad.data[nextpoint+0]!=active_color_r
                    || imgDatad.data[nextpoint+1]!=active_color_g
                    || imgDatad.data[nextpoint+2]!=active_color_b){
                    imgDatad.data[nextpoint+0]=active_color_r
                    imgDatad.data[nextpoint+1]=active_color_g
                    imgDatad.data[nextpoint+2]=active_color_b
                    imgDatad.data[nextpoint+3]=opacity;
                    stack.push([nextX, nextY]);
                    }

            }
        }
        ctx.putImageData(imgDatad,0,0);
        }

    }    

    $('#tools_sketch').click(function(e){
        var fill_switch = document.getElementById('fillregion').innerHTML;
        if (fill_switch == "Fill (on)") {
            painter.paint(e);
        }
    })

    $("#tools_sketch").mousedown(function(e){
        var fill_switch = document.getElementById('fillregion').innerHTML;
        if (fill_switch == "Fill (off)") {
            pencil[e.type](e);
        }
    })

    $("#tools_sketch").mousemove(function(e){
        var fill_switch = document.getElementById('fillregion').innerHTML;
        if (fill_switch == "Fill (off)") {
            pencil[e.type](e);
        }
    })


    $("#tools_sketch").mouseup(function(e){
        var fill_switch = document.getElementById('fillregion').innerHTML;
        if (fill_switch == "Fill (off)") {
            pencil[e.type](e);
        }
    })
})
