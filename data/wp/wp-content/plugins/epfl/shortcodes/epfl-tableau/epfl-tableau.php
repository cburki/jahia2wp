<?php
/**
* Plugin Name: EPFL tableau
* Description: Provide a way to show charts from tableau.epfl.ch
* @version: 1.0
* @copyright: Copyright (c) 2018 Ecole Polytechnique Federale de Lausanne, Switzerland
*/

namespace Epfl\Tableau;

require_once 'shortcake-config.php';

function process_shortcode($atts) {
    if (array_key_exists('embed_code', $atts)) {
        # from a copy-paste of a embed view, parse this information :
        # the view url, the width and the height
        $embed_code = urldecode($atts['embed_code']);

        $dom = new \DOMDocument();
        if ($dom->loadHTML()) {  // valid
            $dom_object = $dom->getElementsByTagName("object");
   
            $width = $dom_object[0]->getAttribute('width');
            $height = $dom_object[0]->getAttribute('height');

            foreach($dom->getElementsByTagName("param") as $param) {
                if ($param->getAttribute('name') === 'name') {
                    $url = $param->getAttribute('value');
                }
            }
        }
    } else {
        # or get the already set url, width and height
        $url = $atts['url'];
        $width = $atts['width'];
        $height = $atts['height'];
    }

    // sanitize what we get
    $url = sanitize_text_field($url);
    $width = sanitize_text_field($width);
    $height = sanitize_text_field($height);

    if (has_action("epfl_tableau_action")) {
        ob_start();
        try {
           do_action("epfl_tableau_action", $url, $width, $height);
           return ob_get_contents();
        } finally {
            ob_end_clean();
        }
    // otherwise the plugin does the rendering
    } else {
        return 'You must activate the epfl theme';
    }
}

add_action( 'register_shortcode_ui', __NAMESPACE__ . '\ShortCake\config');

add_action( 'init', function() {
    // define the shortcode
   add_shortcode('epfl_tableau', __NAMESPACE__ . '\process_shortcode');
});