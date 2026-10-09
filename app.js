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

  var reviewRoot=document.getElementById("expert-review-cards");
  var reviewSection=document.getElementById("qa-expert-reviews");
  var data=window.ParentWiseExpertReviewData;

  if(reviewRoot&&reviewSection){
    var host=(window.location.hostname||"").toLowerCase();
    var safeData=!!data &&
      data.environment==="qa" &&
      data.placeholderContent===true &&
      Array.isArray(data.qaHosts) &&
      data.qaHosts.indexOf(host)!==-1 &&
      Array.isArray(data.reviewers) &&
      data.reviewers.every(function(r){return r&&r.fictional===true;});

    if(!safeData){
      reviewSection.hidden=true;
      console.error("ParentWise safeguard: QA placeholder expert reviews blocked on this host.");
    }else{
      var esc=function(value){
        return String(value==null?"":value)
          .replace(/&/g,"&amp;")
          .replace(/</g,"&lt;")
          .replace(/>/g,"&gt;")
          .replace(/"/g,"&quot;")
          .replace(/'/g,"&#039;");
      };

      reviewRoot.innerHTML=data.reviewers.map(function(r){
        return '<section class="reviewer-card qa-review-card" lang="am" data-fictional-review="true">'+
          '<div class="reviewer-top">'+
            '<div class="reviewer-avatar" aria-hidden="true">'+esc(r.avatarInitials)+'</div>'+
            '<div class="reviewer-identity">'+
              '<span class="placeholder-badge">QA · FICTIONAL SAMPLE</span>'+
              '<h4>'+esc(r.name)+'</h4>'+
              '<p class="reviewer-role-am">'+esc(r.role)+'</p>'+
              '<p class="reviewer-role-en" lang="en">'+esc(r.englishRole)+'</p>'+
              '<p class="reviewer-date">'+esc(r.reviewDate)+'</p>'+
            '</div>'+
          '</div>'+
          '<blockquote class="reviewer-quote">'+esc(r.review)+'</blockquote>'+
          '<div class="reviewer-disclaimer">'+esc(data.disclaimer)+'</div>'+
        '</section>';
      }).join("");
    }
  }
});