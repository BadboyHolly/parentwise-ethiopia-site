/* Isolated landing-page preview interaction. No checkout/API or payment changes. */
(function(){
  "use strict";
  function ready(){
    const toggle=document.querySelector(".option5-menu-toggle");
    const menu=document.getElementById("option5-mobile-nav");
    if(toggle&&menu){
      function close(){
        menu.hidden=true;
        toggle.setAttribute("aria-expanded","false");
        toggle.setAttribute("aria-label","Open navigation menu");
      }
      toggle.addEventListener("click",function(){
        const opening=menu.hidden;
        menu.hidden=!opening;
        toggle.setAttribute("aria-expanded",String(opening));
        toggle.setAttribute("aria-label",opening?"Close navigation menu":"Open navigation menu");
      });
      menu.querySelectorAll("a").forEach(function(link){link.addEventListener("click",close)});
      document.addEventListener("keydown",function(event){
        if(event.key==="Escape"&&!menu.hidden){close();toggle.focus();}
      });
      document.addEventListener("click",function(event){
        if(!menu.hidden&&!menu.contains(event.target)&&!toggle.contains(event.target))close();
      });
    }
    const dialog=document.getElementById("option5-intro-dialog");
    const trigger=document.getElementById("option5-intro-open");
    const closeButton=dialog&&dialog.querySelector("[data-intro-close]");
    const player=document.getElementById("option5-intro-player");
    const empty=document.getElementById("option5-video-unavailable");
    if(!dialog||!trigger||!closeButton||!player||!empty)return;
    // Connect the founder-approved URL later by setting data-video-src on #option5-intro-player.
    // Empty sources never attempt playback; the preview explains what is missing.
    const approvedSrc=player.getAttribute("data-video-src");
    if(approvedSrc){
      try{
        const url=new URL(approvedSrc,location.href);
        if(url.protocol==="https:"||url.origin===location.origin){
          player.src=url.href;
          player.hidden=false;
          empty.hidden=true;
        }
      }catch(_error){/* keep safe explanatory fallback */}
    }
    let lastFocus=null;
    trigger.addEventListener("click",function(){
      lastFocus=document.activeElement;
      if(typeof dialog.showModal==="function"){dialog.showModal();}
      else {dialog.setAttribute("open","");}
      closeButton.focus();
    });
    function closeDialog(){
      player.pause();
      if(typeof dialog.close==="function"&&dialog.open)dialog.close();
      else dialog.removeAttribute("open");
      if(lastFocus&&typeof lastFocus.focus==="function")lastFocus.focus();
    }
    closeButton.addEventListener("click",closeDialog);
    dialog.addEventListener("click",function(event){if(event.target===dialog)closeDialog();});
    dialog.addEventListener("close",function(){player.pause();if(lastFocus&&typeof lastFocus.focus==="function")lastFocus.focus();});
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",ready);
  else ready();
})();