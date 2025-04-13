document.addEventListener('DOMContentLoaded', function() {
  // Sample data - this would be replaced with actual data from your site
  const sampleData = {
    'research-talks': [
      {
        title: 'Quantum Error Mitigation in NISQ Devices',
        date: '2023-05-15',
        tags: ['quantum-computing', 'error-mitigation', 'nisq'],
        path: '/content/research-talks/quantum-error-mitigation.html',
        thumbnail: '/_assets/images/thumbnails/quantum-error-mitigation.jpg'
      },
      // More items would be here
    ],
    'educational': [
      {
        title: 'Introduction to Quantum Computing',
        date: '2022-07-10',
        tags: ['quantum-computing', 'educational', 'fundamentals'],
        path: '/content/educational/intro-quantum-computing.html',
        thumbnail: '/_assets/images/thumbnails/intro-quantum.jpg'
      },
      // More items would be here
    ],
    'tech-notes': [
      {
        title: 'Technical Analysis of Superconducting Qubit Design',
        date: '2023-01-20',
        tags: ['qubit-design', 'hardware', 'superconducting'],
        path: '/content/tech-notes/superconducting-qubit-design.html',
        thumbnail: '/_assets/images/thumbnails/qubit-design.jpg'
      },
      // More items would be here
    ]
  };
  
  // Function to populate items in a category page
  function populateCategoryItems(category) {
    const container = document.getElementById('items-container');
    if (!container) return;
    
    const items = sampleData[category] || [];
    
    items.forEach(item => {
      const itemElement = document.createElement('a');
      itemElement.href = item.path;
      itemElement.classList.add('collection-item');
      itemElement.setAttribute('data-tags', item.tags.join(','));
      
      const thumbnail = document.createElement('div');
      thumbnail.classList.add('item-thumbnail');
      
      if (item.thumbnail) {
        const img = document.createElement('img');
        img.src = item.thumbnail;
        img.alt = item.title;
        thumbnail.appendChild(img);
      } else {
        thumbnail.innerHTML = '<div class="placeholder-thumbnail">No Preview</div>';
      }
      
      const details = document.createElement('div');
      details.classList.add('item-details');
      
      const title = document.createElement('h3');
      title.textContent = item.title;
      
      const meta = document.createElement('p');
      meta.classList.add('meta');
      meta.textContent = new Date(item.date).toLocaleDateString('en-US', { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
      });
      
      const tags = document.createElement('div');
      tags.classList.add('tags');
      
      item.tags.forEach(tag => {
        const tagSpan = document.createElement('span');
        tagSpan.classList.add('tag');
        tagSpan.textContent = tag;
        tags.appendChild(tagSpan);
      });
      
      details.appendChild(title);
      details.appendChild(meta);
      details.appendChild(tags);
      
      itemElement.appendChild(thumbnail);
      itemElement.appendChild(details);
      
      container.appendChild(itemElement);
    });
    
    // Populate tag filter
    populateTagFilter(category);
  }
  
  // Function to populate tag filter dropdown
  function populateTagFilter(category) {
    const filter = document.getElementById('tag-filter');
    if (!filter) return;
    
    const items = sampleData[category] || [];
    const allTags = new Set();
    
    items.forEach(item => {
      item.tags.forEach(tag => allTags.add(tag));
    });
    
    const sortedTags = Array.from(allTags).sort();
    
    sortedTags.forEach(tag => {
      const option = document.createElement('option');
      option.value = tag;
      option.textContent = tag;
      filter.appendChild(option);
    });
    
    // Add event listener
    filter.addEventListener('change', function() {
      const selectedTag = this.value;
      filterItemsByTag(selectedTag);
    });
  }
  
  // Function to filter items by tag
  function filterItemsByTag(tag) {
    const items = document.querySelectorAll('.collection-item');
    
    items.forEach(item => {
      const itemTags = item.getAttribute('data-tags');
      
      if (!tag || itemTags.includes(tag)) {
        item.style.display = 'flex';
      } else {
        item.style.display = 'none';
      }
    });
  }
  
  // Function to populate featured items on the home page
  function populateFeaturedItems() {
    const container = document.getElementById('featured-container');
    if (!container) return;
    
    // Get one item from each category
    const featuredItems = [];
    for (const category in sampleData) {
      if (sampleData[category].length > 0) {
        featuredItems.push(sampleData[category][0]);
      }
    }
    
    featuredItems.forEach(item => {
      const itemElement = document.createElement('a');
      itemElement.href = item.path;
      itemElement.classList.add('featured-item');
      
      const thumbnail = document.createElement('div');
      thumbnail.classList.add('item-thumbnail');
      
      if (item.thumbnail) {
        const img = document.createElement('img');
        img.src = item.thumbnail;
        img.alt = item.title;
        thumbnail.appendChild(img);
      } else {
        thumbnail.innerHTML = '<div class="placeholder-thumbnail">No Preview</div>';
      }
      
      const title = document.createElement('h3');
      title.textContent = item.title;
      
      itemElement.appendChild(thumbnail);
      itemElement.appendChild(title);
      
      container.appendChild(itemElement);
    });
  }
  
  // Function to populate tag cloud on the home page
  function populateTagCloud() {
    const container = document.getElementById('tag-cloud');
    if (!container) return;
    
    const allTags = new Set();
    
    for (const category in sampleData) {
      sampleData[category].forEach(item => {
        item.tags.forEach(tag => allTags.add(tag));
      });
    }
    
    const sortedTags = Array.from(allTags).sort();
    
    sortedTags.forEach(tag => {
      const tagElement = document.createElement('a');
      tagElement.href = '#';
      tagElement.classList.add('tag');
      tagElement.textContent = tag;
      
      tagElement.addEventListener('click', function(e) {
        e.preventDefault();
        // You would implement tag search/filtering here
        console.log('Tag clicked:', tag);
      });
      
      container.appendChild(tagElement);
    });
  }
  
  // Determine what page we're on and call appropriate functions
  const path = window.location.pathname;
  
  if (path.includes('/research-talks')) {
    populateCategoryItems('research-talks');
  } else if (path.includes('/educational')) {
    populateCategoryItems('educational');
  } else if (path.includes('/tech-notes')) {
    populateCategoryItems('tech-notes');
  } else if (path === '/' || path.includes('/index.html')) {
    populateFeaturedItems();
    populateTagCloud();
  }
  
  // Add search functionality
  const searchInput = document.getElementById('search-input');
  if (searchInput) {
    searchInput.addEventListener('input', function() {
      const query = this.value.toLowerCase();
      const items = document.querySelectorAll('.collection-item');
      
      items.forEach(item => {
        const title = item.querySelector('h3').textContent.toLowerCase();
        
        if (title.includes(query)) {
          item.style.display = 'flex';
        } else {
          item.style.display = 'none';
        }
      });
    });
  }
});