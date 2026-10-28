
 ///// funcao para corrigir os casmpos que somem do vinculo
    function combo_tipo(){
        if ($('#id_tipo').length) {
            if ($('#id_tipo').val() === ''){return;}
            if ($('#id_tipo').val() == "Servidor Físico") {
                $(".field-marca").show();
                $(".field-modelo").show();
                $(".field-serie").show();
                $(".field-patrimonio").show();
                $(".field-garantia").show();
                $(".field-vinculado").show();
                $(".field-consumo").show();
            } else {
                $(".field-marca").hide();
                $(".field-modelo").hide();
                $(".field-serie").hide();
                $(".field-patrimonio").hide();
                $(".field-garantia").hide();
                $(".field-vinculado").hide();
                $(".field-consumo").hide();
            }
        }
    }

$(document).ready(function(){
    combo_tipo()
    $("#id_servidorhostnameip_set-0-DELETE").hide();
    $("select#id_tipo").change(function() {
        combo_tipo()
    });
});

