
/*
 * Copyright 2017-present Open Networking Foundation

 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at

 * http://www.apache.org/licenses/LICENSE-2.0

 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */


'use strict';

(function () {
    var configure, highlightBlock;

    configure = hljs.configure;
    // "extending" hljs.configure method
    hljs.configure = function _configure (options) {
        var size = options.highlightSizeThreshold;

        // added highlightSizeThreshold option to set maximum size
        // of processed string. Set to null if not a number
        hljs.highlightSizeThreshold = size === +size ? size : null;

        configure.call(this, options);
    };

    highlightBlock = hljs.highlightBlock;

    // "extending" hljs.highlightBlock method
    hljs.highlightBlock = function _highlightBlock (el) {
        var innerHTML = el.innerHTML;
        var size = hljs.highlightSizeThreshold;

        // check if highlightSizeThreshold is not set or element innerHTML
        // is less than set option highlightSizeThreshold
        if (size == null || size > innerHTML.length) {
            // proceed with hljs.highlightBlock
            highlightBlock.call(hljs, el);
        }
    };

})();

