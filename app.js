document.addEventListener("DOMContentLoaded",function(){
  var bar=document.querySelector(".mobile-buybar");
  var hero=document.querySelector(".hero");
  if(bar&&hero){
    bar.classList.add("is-hidden");
    var io=new IntersectionObserver(function(entries){
      entries.forEach(function(entry){bar.classList.toggle("is-hidden",entry.isIntersecting);});
    },{threshold:0.05});
    io.observe(hero);
  }
});