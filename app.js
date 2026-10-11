/* ParentWise Option 5: independent landing-page interactions only.
   No payment, backend, checkout, API or browser storage functionality. */
(function(){
  "use strict";
  function ready(){
    var menu=document.getElementById("option5-mobile-nav");
    var toggle=document.querySelector(".option5-menu-toggle");
    function closeMenu(){
      if(!menu||!toggle)return;
      menu.hidden=true;
      toggle.setAttribute("aria-expanded","false");
      toggle.setAttribute("aria-label","Open navigation menu");
    }
    if(menu&&toggle){
      toggle.addEventListener("click",function(){
        var open=menu.hidden;
        menu.hidden=!open;
        toggle.setAttribute("aria-expanded",String(open));
        toggle.setAttribute("aria-label",open?"Close navigation menu":"Open navigation menu");
      });
      menu.querySelectorAll("a").forEach(function(a){a.addEventListener("click",closeMenu);});
      document.addEventListener("keydown",function(e){if(e.key==="Escape"&&!menu.hidden){closeMenu();toggle.focus();}});
      document.addEventListener("click",function(e){if(!menu.hidden&&!menu.contains(e.target)&&!toggle.contains(e.target))closeMenu();});
    }

    var bar=document.querySelector(".mobile-buybar");
    var hero=document.querySelector(".hero");
    if(bar&&hero){
      bar.classList.add("is-hidden");
      if("IntersectionObserver" in window){
        var observer=new IntersectionObserver(function(entries){
          entries.forEach(function(entry){bar.classList.toggle("is-hidden",entry.isIntersecting);});
        },{threshold:.03});
        observer.observe(hero);
      }else bar.classList.remove("is-hidden");
    }

    var dialog=document.getElementById("option5-intro-dialog");
    var openButton=document.getElementById("option5-intro-open");
    var closeButton=dialog&&dialog.querySelector("[data-intro-close]");
    var player=document.getElementById("option5-intro-player");
    var absent=document.getElementById("option5-video-unavailable");
    if(!dialog||!openButton||!closeButton||!player||!absent)return;
    var approvedSrc=player.getAttribute("data-video-src");
    if(approvedSrc){
      try{
        var u=new URL(approvedSrc,window.location.href);
        if(u.protocol==="https:"||u.origin===window.location.origin){
          player.src=u.href;
          player.hidden=false;
          absent.hidden=true;
        }
      }catch(err){/* Keep honest missing-video text. */}
    }
    var lastFocus=null;
    function hide(){
      player.pause();
      if(typeof dialog.close==="function"&&dialog.open)dialog.close();else dialog.removeAttribute("open");
      if(lastFocus&&typeof lastFocus.focus==="function")lastFocus.focus();
    }
    openButton.addEventListener("click",function(){
      lastFocus=document.activeElement;
      if(typeof dialog.showModal==="function")dialog.showModal();else dialog.setAttribute("open","");
      closeButton.focus();
    });
    closeButton.addEventListener("click",hide);
    dialog.addEventListener("click",function(e){if(e.target===dialog)hide();});
    dialog.addEventListener("close",function(){player.pause();if(lastFocus&&typeof lastFocus.focus==="function")lastFocus.focus();});
  }
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",ready);
  else ready();
})();