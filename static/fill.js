$(function(){
    var canvas = $('#tools_sketch')[0];
    var ctx = canvas.getContext('2d');
    var width = canvas.width;
    var height = canvas.height;
    var alpha_value = 153;
//    updateAlpha()

    var active_color = "rgb(255,0,0)";
    var active_color_r = 255;
    var active_color_g = 0;
    var active_color_b = 0;
    var pencil_size = 2;

    var tempimgData = [ctx.getImageData(0,0,width,height)];


//    $("#opacity_slider").slider({
//        ticks: [0.2, 0.4, 0.6, 0.8],
//        ticks_labels: ["0.2", "0.4", "0.6", "0.8"],
//        ticks_snap_bounds: 0.1,
//        step: 0.1,
//        value: 0.6
//    })
//
//
//    $("#opacity_slider").on('slideStop', function(e){
//        alpha_value= e.value * 255;
//        updateAlpha();
//    })

    $("#undo_btn").on("click", function(){
        ctx.putImageData(tempimgData.pop(),0,0);
        if (tempimgData.length==0){
            document.getElementById('undo_btn').disabled = true
        }
    })


    function update_undo_stack(){
        tempimgData.push(ctx.getImageData(0,0,width,height));
        document.getElementById('undo_btn').disabled = false
    }

    function isApprox(a, b, range) {
              var d = a - b;
              return d < range && d > -range;
            }

    $(".size_btn").on("click", function(){
        pencil_size = $(this).attr('data-size');
        $(this).siblings().removeClass('active'); // To make other button inactive
        $(this).addClass("active");
        return false; // This button won't submit the form.
    })

    $(".eraser").on("click", function(){
        active_color= "rgba(0,0,0,1)";
        ctx.globalCompositeOperation = "destination-out";
        $("#paint")[0].disabled=true
    })

    $(".select_color").on("click", function(){
        active_color= $(this).attr('data-color');
        regex_match = active_color.match(/[0-9]+/g)
        active_color_r = parseInt(regex_match[0])
        active_color_g = parseInt(regex_match[1])
        active_color_b = parseInt(regex_match[2])
        ctx.globalCompositeOperation = "source-over";
        $("#paint")[0].disabled=false

        // Remove all colors of the entire panel 
        var rmp = document.getElementById('rm_panel').checked;
            if(rmp){
                update_undo_stack()
            
            var canvasData = ctx.getImageData(0, 0, width, height);

            pix = canvasData.data;
            // for (var i = 0, n = pix.length; i <n; i += 4) {
            //     if(pix[i] === active_color_r && pix[i+1] === active_color_g && pix[i+2] === active_color_b){
            //          pix[i+3] = 0;   
            //     }
            // }
            for (var i = 0, n = pix.length; i <n; i += 4) {
                if(isApprox(pix[i], active_color_r, 5) &&
                   isApprox(pix[i+1], active_color_g, 5) &&
                   isApprox(pix[i+2], active_color_b, 5)){
                     pix[i+3] = 0;   
                }
            }
            ctx.putImageData(canvasData, 0, 0);
            document.getElementById('rm_panel').checked = false;
                }}
    )

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
                tool.started=false;
            }
        }

        $(canvas).on("mouseleave", function(){
            tool.started = false;
        })

        $(canvas).on("mouseout", function(){
            tool.started = false;
        })


    }


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
                    imgDatad.data[nextpoint+3]=255;
                    stack.push([nextX, nextY]);
                    }

            }
        }
        ctx.putImageData(imgDatad,0,0);
        document.getElementById('paint').checked = false;
        }

   }

    $('#tools_sketch').click(function(e){
    var fill = document.getElementById('paint').checked
    if(fill){
        painter.paint(e)
    }
    })

    $("#tools_sketch").mousedown(function(e){
    var fill = document.getElementById('paint').checked;
    if (fill==false){
        pencil[e.type](e);
    }

    })

    $("#tools_sketch").mousemove(function(e){
    var fill = document.getElementById('paint').checked;
    if (fill==false){
        pencil[e.type](e);
    }
    })


    $("#tools_sketch").mouseup(function(e){
    var fill = document.getElementById('paint').checked;
    if (fill==false){
        pencil[e.type](e);
    }
    })
})
