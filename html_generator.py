import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
import json
from datetime import datetime
from database import db_manager
from config import HTML_CONFIG

class HTMLGenerator:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.template_folder = Path(HTML_CONFIG['template_folder'])
        self.output_folder = Path(HTML_CONFIG['output_folder'])
        
        # Create directories if they don't exist
        self.template_folder.mkdir(parents=True, exist_ok=True)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        # Setup Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(self.template_folder)),
            autoescape=True
        )
        
        # Create default templates if they don't exist
        self.create_default_templates()
    
    def create_default_templates(self):
        """Create default HTML templates"""
        templates = {
            'base.html': self._get_base_template(),
            'index.html': self._get_index_template(),
            'software_list.html': self._get_software_list_template(),
            'software_detail.html': self._get_software_detail_template(),
            'category.html': self._get_category_template()
        }
        
        for template_name, content in templates.items():
            template_path = self.template_folder / template_name
            if not template_path.exists():
                with open(template_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                self.logger.info(f"Created template: {template_name}")
    
    def _get_base_template(self) -> str:
        """Get base HTML template"""
        return '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Freeware Collection{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
    <style>
        .software-card {
            transition: transform 0.2s;
            height: 100%;
        }
        .software-card:hover {
            transform: translateY(-5px);
        }
        .download-links a {
            margin-right: 10px;
            margin-bottom: 5px;
        }
        .stats-card {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        .category-badge {
            font-size: 0.8rem;
        }
        .navbar-brand {
            font-weight: bold;
        }
        footer {
            background-color: #343a40;
            color: white;
            margin-top: 50px;
        }
        .search-box {
            max-width: 500px;
        }
    </style>
    {% block extra_css %}{% endblock %}
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="index.html">
                <i class="fas fa-download"></i> Freeware Collection
            </a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav me-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="index.html">Home</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="software_list.html">All Software</a>
                    </li>
                    <li class="nav-item dropdown">
                        <a class="nav-link dropdown-toggle" href="#" id="navbarDropdown" role="button" data-bs-toggle="dropdown">
                            Categories
                        </a>
                        <ul class="dropdown-menu">
                            <li><a class="dropdown-item" href="category_windows.html">Windows</a></li>
                            <li><a class="dropdown-item" href="category_macos.html">macOS</a></li>
                            <li><a class="dropdown-item" href="category_android.html">Android</a></li>
                            <li><a class="dropdown-item" href="category_games.html">Games</a></li>
                        </ul>
                    </li>
                </ul>
                <div class="d-flex search-box">
                    <input class="form-control me-2" type="search" id="searchInput" placeholder="Search software...">
                </div>
            </div>
        </div>
    </nav>

    <main class="container mt-4">
        {% block content %}{% endblock %}
    </main>

    <footer class="py-4">
        <div class="container">
            <div class="row">
                <div class="col-md-6">
                    <h5>Freeware Collection</h5>
                    <p>Curated collection of free software from trusted sources.</p>
                </div>
                <div class="col-md-6 text-end">
                    <p>Last updated: {{ last_updated }}</p>
                    <p>Total software: {{ total_count }}</p>
                </div>
            </div>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // Simple search functionality
        document.getElementById('searchInput').addEventListener('input', function(e) {
            const searchTerm = e.target.value.toLowerCase();
            const softwareCards = document.querySelectorAll('.software-card');
            
            softwareCards.forEach(card => {
                const title = card.querySelector('.card-title').textContent.toLowerCase();
                const description = card.querySelector('.card-text').textContent.toLowerCase();
                
                if (title.includes(searchTerm) || description.includes(searchTerm)) {
                    card.parentElement.style.display = 'block';
                } else {
                    card.parentElement.style.display = 'none';
                }
            });
        });
    </script>
    {% block extra_js %}{% endblock %}
</body>
</html>'''
    
    def _get_index_template(self) -> str:
        """Get index page template"""
        return '''{% extends "base.html" %}

{% block title %}Freeware Collection - Home{% endblock %}

{% block content %}
<div class="hero-section text-center py-5 mb-5" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px;">
    <h1 class="display-4">Welcome to Freeware Collection</h1>
    <p class="lead">Discover and download the best free software</p>
    <p>{{ total_software }} software packages from {{ total_sources }} trusted sources</p>
</div>

<div class="row mb-4">
    <div class="col-md-3 mb-3">
        <div class="card stats-card text-center">
            <div class="card-body">
                <i class="fas fa-download fa-2x mb-2"></i>
                <h4>{{ stats.total_downloads }}</h4>
                <p class="mb-0">Total Downloads</p>
            </div>
        </div>
    </div>
    <div class="col-md-3 mb-3">
        <div class="card stats-card text-center">
            <div class="card-body">
                <i class="fas fa-apps fa-2x mb-2"></i>
                <h4>{{ stats.total_software }}</h4>
                <p class="mb-0">Software Packages</p>
            </div>
        </div>
    </div>
    <div class="col-md-3 mb-3">
        <div class="card stats-card text-center">
            <div class="card-body">
                <i class="fas fa-tags fa-2x mb-2"></i>
                <h4>{{ stats.total_categories }}</h4>
                <p class="mb-0">Categories</p>
            </div>
        </div>
    </div>
    <div class="col-md-3 mb-3">
        <div class="card stats-card text-center">
            <div class="card-body">
                <i class="fas fa-clock fa-2x mb-2"></i>
                <h4>{{ stats.last_updated }}</h4>
                <p class="mb-0">Last Updated</p>
            </div>
        </div>
    </div>
</div>

<h2 class="mb-4">Latest Software</h2>
<div class="row">
    {% for software in latest_software %}
    <div class="col-md-4 mb-4">
        <div class="card software-card">
            <div class="card-body">
                <h5 class="card-title">{{ software.title }}</h5>
                <p class="card-text">{{ software.description[:150] }}{% if software.description|length > 150 %}...{% endif %}</p>
                <div class="mb-2">
                    <span class="badge bg-primary category-badge">{{ software.category or 'General' }}</span>
                    {% if software.version %}
                    <span class="badge bg-secondary category-badge">v{{ software.version }}</span>
                    {% endif %}
                    {% if software.file_size %}
                    <span class="badge bg-info category-badge">{{ software.file_size }}</span>
                    {% endif %}
                </div>
                <div class="download-links">
                    {% if software.cloud_links %}
                        {% for provider, link in software.cloud_links.items() %}
                            {% if link %}
                            <a href="{{ link }}" class="btn btn-sm btn-outline-primary" target="_blank">
                                <i class="fas fa-cloud-download-alt"></i> {{ provider.title() }}
                            </a>
                            {% endif %}
                        {% endfor %}
                    {% endif %}
                </div>
                <small class="text-muted">Source: {{ software.source_site }}</small>
            </div>
        </div>
    </div>
    {% endfor %}
</div>

<div class="text-center mt-4">
    <a href="software_list.html" class="btn btn-primary btn-lg">View All Software</a>
</div>
{% endblock %}'''
    
    def _get_software_list_template(self) -> str:
        """Get software list template"""
        return '''{% extends "base.html" %}

{% block title %}All Software - Freeware Collection{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-4">
    <h1>All Software ({{ software_list|length }})</h1>
    <div class="btn-group" role="group">
        <button type="button" class="btn btn-outline-primary" onclick="sortBy('title')">
            <i class="fas fa-sort-alpha-down"></i> Name
        </button>
        <button type="button" class="btn btn-outline-primary" onclick="sortBy('category')">
            <i class="fas fa-tags"></i> Category
        </button>
        <button type="button" class="btn btn-outline-primary" onclick="sortBy('date')">
            <i class="fas fa-calendar"></i> Date
        </button>
    </div>
</div>

<div class="row" id="softwareContainer">
    {% for software in software_list %}
    <div class="col-md-4 mb-4 software-item" data-category="{{ software.category or 'general' }}" data-title="{{ software.title }}" data-date="{{ software.scraped_date }}">
        <div class="card software-card">
            <div class="card-body">
                <h5 class="card-title">{{ software.title }}</h5>
                <p class="card-text">{{ software.description[:100] }}{% if software.description|length > 100 %}...{% endif %}</p>
                <div class="mb-2">
                    <span class="badge bg-primary category-badge">{{ software.category or 'General' }}</span>
                    {% if software.version %}
                    <span class="badge bg-secondary category-badge">v{{ software.version }}</span>
                    {% endif %}
                    {% if software.file_size %}
                    <span class="badge bg-info category-badge">{{ software.file_size }}</span>
                    {% endif %}
                </div>
                <div class="download-links">
                    {% if software.cloud_links %}
                        {% for provider, link in software.cloud_links.items() %}
                            {% if link %}
                            <a href="{{ link }}" class="btn btn-sm btn-outline-primary" target="_blank">
                                <i class="fas fa-cloud-download-alt"></i> {{ provider.title() }}
                            </a>
                            {% endif %}
                        {% endfor %}
                    {% endif %}
                </div>
                <div class="mt-2">
                    <small class="text-muted">
                        Source: {{ software.source_site }} | 
                        Added: {{ software.scraped_date.strftime('%Y-%m-%d') if software.scraped_date else 'Unknown' }}
                    </small>
                </div>
            </div>
        </div>
    </div>
    {% endfor %}
</div>

{% if software_list|length == 0 %}
<div class="text-center py-5">
    <i class="fas fa-search fa-3x text-muted mb-3"></i>
    <h3>No software found</h3>
    <p class="text-muted">Try adjusting your search or check back later for new software.</p>
</div>
{% endif %}
{% endblock %}

{% block extra_js %}
<script>
function sortBy(criteria) {
    const container = document.getElementById('softwareContainer');
    const items = Array.from(container.querySelectorAll('.software-item'));
    
    items.sort((a, b) => {
        let aValue, bValue;
        
        switch(criteria) {
            case 'title':
                aValue = a.getAttribute('data-title').toLowerCase();
                bValue = b.getAttribute('data-title').toLowerCase();
                break;
            case 'category':
                aValue = a.getAttribute('data-category').toLowerCase();
                bValue = b.getAttribute('data-category').toLowerCase();
                break;
            case 'date':
                aValue = new Date(a.getAttribute('data-date') || '1970-01-01');
                bValue = new Date(b.getAttribute('data-date') || '1970-01-01');
                return bValue - aValue; // Newest first
        }
        
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
    });
    
    // Clear and re-append sorted items
    container.innerHTML = '';
    items.forEach(item => container.appendChild(item));
}
</script>
{% endblock %}'''
    
    def _get_software_detail_template(self) -> str:
        """Get software detail template"""
        return '''{% extends "base.html" %}

{% block title %}{{ software.title }} - Freeware Collection{% endblock %}

{% block content %}
<nav aria-label="breadcrumb" class="mb-4">
    <ol class="breadcrumb">
        <li class="breadcrumb-item"><a href="index.html">Home</a></li>
        <li class="breadcrumb-item"><a href="software_list.html">Software</a></li>
        <li class="breadcrumb-item active">{{ software.title }}</li>
    </ol>
</nav>

<div class="row">
    <div class="col-md-8">
        <h1>{{ software.title }}</h1>
        
        <div class="mb-3">
            <span class="badge bg-primary me-2">{{ software.category or 'General' }}</span>
            {% if software.version %}
            <span class="badge bg-secondary me-2">Version {{ software.version }}</span>
            {% endif %}
            {% if software.file_size %}
            <span class="badge bg-info me-2">{{ software.file_size }}</span>
            {% endif %}
        </div>
        
        <div class="card mb-4">
            <div class="card-body">
                <h5 class="card-title">Description</h5>
                <p class="card-text">{{ software.description or 'No description available.' }}</p>
            </div>
        </div>
        
        {% if software.metadata and software.metadata.requirements %}
        <div class="card mb-4">
            <div class="card-body">
                <h5 class="card-title">System Requirements</h5>
                <ul class="list-unstyled">
                    {% for req_type, req_value in software.metadata.requirements.items() %}
                    <li><strong>{{ req_type.title() }}:</strong> {{ req_value }}</li>
                    {% endfor %}
                </ul>
            </div>
        </div>
        {% endif %}
        
        {% if software.metadata and software.metadata.screenshots %}
        <div class="card mb-4">
            <div class="card-body">
                <h5 class="card-title">Screenshots</h5>
                <div class="row">
                    {% for screenshot in software.metadata.screenshots[:4] %}
                    <div class="col-md-6 mb-3">
                        <img src="{{ screenshot }}" class="img-fluid rounded" alt="Screenshot">
                    </div>
                    {% endfor %}
                </div>
            </div>
        </div>
        {% endif %}
    </div>
    
    <div class="col-md-4">
        <div class="card">
            <div class="card-body">
                <h5 class="card-title">Download</h5>
                
                {% if software.cloud_links %}
                <div class="mb-3">
                    <h6>Cloud Storage Links:</h6>
                    {% for provider, link in software.cloud_links.items() %}
                        {% if link %}
                        <a href="{{ link }}" class="btn btn-primary btn-block mb-2 d-block" target="_blank">
                            <i class="fas fa-cloud-download-alt"></i> Download from {{ provider.title() }}
                        </a>
                        {% endif %}
                    {% endfor %}
                </div>
                {% endif %}
                
                {% if software.download_links %}
                <div class="mb-3">
                    <h6>Direct Links:</h6>
                    {% for link in software.download_links[:3] %}
                    <a href="{{ link }}" class="btn btn-outline-secondary btn-block mb-2 d-block" target="_blank">
                        <i class="fas fa-download"></i> Mirror {{ loop.index }}
                    </a>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
        </div>
        
        <div class="card mt-3">
            <div class="card-body">
                <h5 class="card-title">Information</h5>
                <ul class="list-unstyled">
                    <li><strong>Source:</strong> {{ software.source_site }}</li>
                    <li><strong>Added:</strong> {{ software.scraped_date.strftime('%Y-%m-%d') if software.scraped_date else 'Unknown' }}</li>
                    {% if software.metadata and software.metadata.author %}
                    <li><strong>Developer:</strong> {{ software.metadata.author }}</li>
                    {% endif %}
                    {% if software.metadata and software.metadata.license %}
                    <li><strong>License:</strong> {{ software.metadata.license }}</li>
                    {% endif %}
                </ul>
            </div>
        </div>
    </div>
</div>
{% endblock %}'''
    
    def _get_category_template(self) -> str:
        """Get category page template"""
        return '''{% extends "base.html" %}

{% block title %}{{ category_name }} Software - Freeware Collection{% endblock %}

{% block content %}
<h1>{{ category_name }} Software ({{ software_list|length }})</h1>
<p class="lead">Free {{ category_name.lower() }} software and applications</p>

<div class="row">
    {% for software in software_list %}
    <div class="col-md-4 mb-4">
        <div class="card software-card">
            <div class="card-body">
                <h5 class="card-title">{{ software.title }}</h5>
                <p class="card-text">{{ software.description[:100] }}{% if software.description|length > 100 %}...{% endif %}</p>
                <div class="mb-2">
                    {% if software.version %}
                    <span class="badge bg-secondary category-badge">v{{ software.version }}</span>
                    {% endif %}
                    {% if software.file_size %}
                    <span class="badge bg-info category-badge">{{ software.file_size }}</span>
                    {% endif %}
                </div>
                <div class="download-links">
                    {% if software.cloud_links %}
                        {% for provider, link in software.cloud_links.items() %}
                            {% if link %}
                            <a href="{{ link }}" class="btn btn-sm btn-outline-primary" target="_blank">
                                <i class="fas fa-cloud-download-alt"></i> {{ provider.title() }}
                            </a>
                            {% endif %}
                        {% endfor %}
                    {% endif %}
                </div>
                <small class="text-muted">Source: {{ software.source_site }}</small>
            </div>
        </div>
    </div>
    {% endfor %}
</div>

{% if software_list|length == 0 %}
<div class="text-center py-5">
    <i class="fas fa-folder-open fa-3x text-muted mb-3"></i>
    <h3>No {{ category_name.lower() }} software found</h3>
    <p class="text-muted">Check back later for new additions.</p>
</div>
{% endif %}
{% endblock %}'''
    
    def generate_index_page(self) -> str:
        """Generate index page"""
        try:
            # Get statistics
            stats = db_manager.get_stats()
            
            # Get latest software
            latest_software = self._get_latest_software(12)
            
            template = self.env.get_template('index.html')
            html_content = template.render(
                stats=stats,
                latest_software=latest_software,
                total_software=stats.get('total_items', 0),
                total_sources=len(stats.get('by_source', {})),
                last_updated=datetime.now().strftime('%Y-%m-%d %H:%M'),
                total_count=stats.get('total_items', 0)
            )
            
            output_path = self.output_folder / 'index.html'
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"Generated index page: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error generating index page: {e}")
            return None
    
    def generate_software_list_page(self) -> str:
        """Generate software list page"""
        try:
            # Get all software
            software_list = self._get_all_software()
            
            template = self.env.get_template('software_list.html')
            html_content = template.render(
                software_list=software_list,
                last_updated=datetime.now().strftime('%Y-%m-%d %H:%M'),
                total_count=len(software_list)
            )
            
            output_path = self.output_folder / 'software_list.html'
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"Generated software list page: {output_path}")
            return str(output_path)
            
        except Exception as e:
            self.logger.error(f"Error generating software list page: {e}")
            return None
    
    def generate_category_pages(self) -> List[str]:
        """Generate category pages"""
        generated_pages = []
        
        try:
            stats = db_manager.get_stats()
            categories = stats.get('by_source', {}).keys()
            
            for category in categories:
                software_list = self._get_software_by_category(category)
                
                template = self.env.get_template('category.html')
                html_content = template.render(
                    category_name=category.title(),
                    software_list=software_list,
                    last_updated=datetime.now().strftime('%Y-%m-%d %H:%M'),
                    total_count=len(software_list)
                )
                
                output_path = self.output_folder / f'category_{category.lower()}.html'
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                
                generated_pages.append(str(output_path))
                self.logger.info(f"Generated category page: {output_path}")
            
            return generated_pages
            
        except Exception as e:
            self.logger.error(f"Error generating category pages: {e}")
            return []
    
    def generate_full_report(self) -> Optional[str]:
        """Generate complete HTML report"""
        try:
            self.logger.info("Starting full HTML report generation")
            
            # Generate all pages
            index_path = self.generate_index_page()
            list_path = self.generate_software_list_page()
            category_paths = self.generate_category_pages()
            
            # Generate CSS and JS files
            self._generate_static_files()
            
            # Create summary report
            summary = {
                'generated_at': datetime.now().isoformat(),
                'pages_generated': {
                    'index': index_path,
                    'software_list': list_path,
                    'categories': category_paths
                },
                'total_pages': 2 + len(category_paths)
            }
            
            summary_path = self.output_folder / 'generation_summary.json'
            with open(summary_path, 'w') as f:
                json.dump(summary, f, indent=2)
            
            self.logger.info(f"Full HTML report generated: {self.output_folder}")
            return str(self.output_folder)
            
        except Exception as e:
            self.logger.error(f"Error generating full report: {e}")
            return None
    
    def _get_latest_software(self, limit: int = 12) -> List[Dict]:
        """Get latest software items"""
        try:
            if not db_manager.connection:
                db_manager.connect()
                
            cursor = db_manager.connection.cursor(dictionary=True)
            cursor.execute('''
                SELECT * FROM software_items 
                WHERE is_active = TRUE 
                ORDER BY scraped_date DESC 
                LIMIT %s
            ''', (limit,))
            
            results = cursor.fetchall()
            cursor.close()
            
            # Parse JSON fields
            for result in results:
                if result.get('download_links'):
                    result['download_links'] = json.loads(result['download_links'])
                if result.get('metadata'):
                    result['metadata'] = json.loads(result['metadata'])
                if result.get('cloud_links'):
                    result['cloud_links'] = json.loads(result['cloud_links'])
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting latest software: {e}")
            return []
    
    def _get_all_software(self) -> List[Dict]:
        """Get all software items"""
        try:
            if not db_manager.connection:
                db_manager.connect()
                
            cursor = db_manager.connection.cursor(dictionary=True)
            cursor.execute('''
                SELECT * FROM software_items 
                WHERE is_active = TRUE 
                ORDER BY title ASC
            ''')
            
            results = cursor.fetchall()
            cursor.close()
            
            # Parse JSON fields
            for result in results:
                if result.get('download_links'):
                    result['download_links'] = json.loads(result['download_links'])
                if result.get('metadata'):
                    result['metadata'] = json.loads(result['metadata'])
                if result.get('cloud_links'):
                    result['cloud_links'] = json.loads(result['cloud_links'])
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting all software: {e}")
            return []
    
    def _get_software_by_category(self, category: str) -> List[Dict]:
        """Get software by category"""
        try:
            if not db_manager.connection:
                db_manager.connect()
                
            cursor = db_manager.connection.cursor(dictionary=True)
            cursor.execute('''
                SELECT * FROM software_items 
                WHERE is_active = TRUE AND source_site = %s
                ORDER BY title ASC
            ''', (category,))
            
            results = cursor.fetchall()
            cursor.close()
            
            # Parse JSON fields
            for result in results:
                if result.get('download_links'):
                    result['download_links'] = json.loads(result['download_links'])
                if result.get('metadata'):
                    result['metadata'] = json.loads(result['metadata'])
                if result.get('cloud_links'):
                    result['cloud_links'] = json.loads(result['cloud_links'])
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error getting software by category: {e}")
            return []
    
    def _generate_static_files(self):
        """Generate additional CSS and JS files"""
        try:
            # Create a simple CSS file for additional styling
            css_content = '''
/* Additional styles for Freeware Collection */
.fade-in {
    animation: fadeIn 0.5s ease-in;
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

.loading {
    display: inline-block;
    width: 20px;
    height: 20px;
    border: 3px solid rgba(255,255,255,.3);
    border-radius: 50%;
    border-top-color: #fff;
    animation: spin 1s ease-in-out infinite;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}
'''
            
            css_path = self.output_folder / 'style.css'
            with open(css_path, 'w') as f:
                f.write(css_content)
            
            self.logger.info(f"Generated CSS file: {css_path}")
            
        except Exception as e:
            self.logger.error(f"Error generating static files: {e}")

# Initialize HTML generator
html_generator = HTMLGenerator()