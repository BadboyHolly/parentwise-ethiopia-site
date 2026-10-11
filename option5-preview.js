/* ParentWise Option 5 rebuild — lightweight frontend only.
   No checkout, admin, payment, delivery or database actions. */
(function(){
 "use strict";
 function init(){
  const toggle=document.querySelector(".menu-button");
  const menu=document.getElementById("mobile-menu");
  if(toggle&&menu){
    function close(restoreFocus){
      menu.hidden=true;
      toggle.setAttribute("aria-expanded","false");
      toggle.setAttribute("aria-label","Open menu");
      if(restoreFocus)toggle.focus();
    }
    toggle.addEventListener("click",function(){
      const opening=menu.hidden;
      menu.hidden=!opening;
      toggle.setAttribute("aria-expanded",String(opening));
      toggle.setAttribute("aria-label",opening?"Close menu":"Open menu");
    });
    menu.querySelectorAll("a").forEach(function(a){a.addEventListener("click",function(){close(false);});});
    document.addEventListener("keydown",function(event){if(event.key==="Escape"&&!menu.hidden)close(true);});
    document.addEventListener("click",function(event){
      if(!menu.hidden&&!menu.contains(event.target)&&!toggle.contains(event.target))close(false);
    });
  }
  const dialog=document.getElementById("option5-intro-dialog");
  const trigger=document.getElementById("option5-intro-open");
  const closeButton=dialog&&dialog.querySelector("[data-intro-close]");
  const player=document.getElementById("option5-intro-player");
  const unavailable=document.getElementById("option5-video-unavailable");
  if(dialog&&trigger&&closeButton&&player&&unavailable){
    const videoSrc=player.getAttribute("data-video-src");
    if(videoSrc){
      try{
        const url=new URL(videoSrc,location.href);
        if(url.protocol==="https:"||url.origin===location.origin){
          player.src=url.href;player.hidden=false;unavailable.hidden=true;
        }
      }catch(e){/* Do not load malformed or unapproved video URLs. */}
    }
    let prior=null;
    trigger.addEventListener("click",function(){
      prior=document.activeElement;
      if(typeof dialog.showModal==="function")dialog.showModal();
      else dialog.setAttribute("open","");
      closeButton.focus();
    });
    function closeDialog(){
      player.pause();
      if(typeof dialog.close==="function"&&dialog.open)dialog.close();
      else dialog.removeAttribute("open");
    }
    closeButton.addEventListener("click",closeDialog);
    dialog.addEventListener("click",function(event){if(event.target===dialog)closeDialog();});
    dialog.addEventListener("close",function(){player.pause();if(prior&&prior.isConnected)prior.focus();});
  }
  const sticky=document.querySelector(".sticky-buy");
  const price=document.querySelector(".offer-card");
  if(sticky&&price&&"IntersectionObserver" in window){
    const observer=new IntersectionObserver(function(entries){
      entries.forEach(function(e){sticky.classList.toggle("is-hidden",e.isIntersecting);});
    },{threshold:0.1});
    observer.observe(price);
  }
 }
 if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",init);
 else init();
})();