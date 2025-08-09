# MCC Portfolio SharePoint Folder Structure Setup Script
# Prerequisites: SharePoint Online PowerShell Module and PnP PowerShell
# Run: Install-Module -Name Microsoft.Online.SharePoint.PowerShell
# Run: Install-Module -Name PnP.PowerShell

param(
    [Parameter(Mandatory=$true)]
    [string]$TenantUrl,  # e.g., "https://markcubancompanies.sharepoint.com"
    
    [Parameter(Mandatory=$true)]
    [string]$SiteUrl,    # e.g., "https://markcubancompanies.sharepoint.com/sites/Portfolio"
    
    [Parameter(Mandatory=$false)]
    [string]$AdminEmail = "admin@markcubancompanies.com"
)

# Import required modules
Import-Module Microsoft.Online.SharePoint.PowerShell -ErrorAction Stop
Import-Module PnP.PowerShell -ErrorAction Stop

Write-Host "🚀 MCC Portfolio SharePoint Setup Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Connect to SharePoint
Write-Host "`n📡 Connecting to SharePoint..." -ForegroundColor Yellow
try {
    Connect-PnPOnline -Url $SiteUrl -Interactive
    Write-Host "✅ Connected to SharePoint" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to connect to SharePoint: $_" -ForegroundColor Red
    exit 1
}

# Define folder structure
$folderStructure = @{
    "Portfolio" = @{
        "_Template" = @(
            "Legal",
            "Finance",
            "Updates",
            "Email-Exports",
            "Notes",
            "Board-Materials",
            "Cap-Tables",
            "Contracts"
        )
    }
}

# Security groups
$securityGroups = @(
    @{
        Name = "MCC-Portfolio-Admins"
        Description = "Full control over portfolio documents"
        Permission = "Full Control"
    },
    @{
        Name = "MCC-Portfolio-Finance"
        Description = "Read/write access to financial documents"
        Permission = "Contribute"
    },
    @{
        Name = "MCC-Portfolio-Legal"
        Description = "Read/write access to legal documents"
        Permission = "Contribute"
    },
    @{
        Name = "MCC-Portfolio-Readers"
        Description = "Read-only access to non-sensitive documents"
        Permission = "Read"
    }
)

# Function to create folders
function Create-FolderStructure {
    param(
        [string]$ParentFolder,
        [array]$SubFolders
    )
    
    foreach ($folder in $SubFolders) {
        $folderPath = if ($ParentFolder) { "$ParentFolder/$folder" } else { $folder }
        
        try {
            # Check if folder exists
            $existingFolder = Get-PnPFolder -Url $folderPath -ErrorAction SilentlyContinue
            
            if ($null -eq $existingFolder) {
                # Create folder
                Add-PnPFolder -Name $folder -Folder $ParentFolder
                Write-Host "  ✅ Created: $folderPath" -ForegroundColor Green
            } else {
                Write-Host "  ⏭️  Exists: $folderPath" -ForegroundColor Yellow
            }
        } catch {
            Write-Host "  ❌ Failed to create $folderPath : $_" -ForegroundColor Red
        }
    }
}

# Function to set folder permissions
function Set-FolderPermissions {
    param(
        [string]$FolderPath,
        [string]$GroupName,
        [string]$Permission
    )
    
    try {
        # Break inheritance if needed
        Set-PnPFolderPermission -List "Documents" -Identity $FolderPath -ClearExistingPermissions
        
        # Add group permission
        Set-PnPFolderPermission -List "Documents" -Identity $FolderPath -Group $GroupName -AddRole $Permission
        
        Write-Host "  🔒 Set permission: $GroupName -> $Permission on $FolderPath" -ForegroundColor Cyan
    } catch {
        Write-Host "  ❌ Failed to set permission on $FolderPath : $_" -ForegroundColor Red
    }
}

# Step 1: Create security groups
Write-Host "`n👥 Creating Security Groups..." -ForegroundColor Yellow
foreach ($group in $securityGroups) {
    try {
        $existingGroup = Get-PnPGroup -Identity $group.Name -ErrorAction SilentlyContinue
        
        if ($null -eq $existingGroup) {
            New-PnPGroup -Title $group.Name -Description $group.Description
            Write-Host "  ✅ Created group: $($group.Name)" -ForegroundColor Green
        } else {
            Write-Host "  ⏭️  Group exists: $($group.Name)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  ❌ Failed to create group $($group.Name): $_" -ForegroundColor Red
    }
}

# Step 2: Create base Portfolio folder
Write-Host "`n📁 Creating Portfolio Base Structure..." -ForegroundColor Yellow
Create-FolderStructure -ParentFolder "Shared Documents" -SubFolders @("Portfolio")

# Step 3: Create template folder structure
Write-Host "`n📁 Creating Template Folder Structure..." -ForegroundColor Yellow
Create-FolderStructure -ParentFolder "Shared Documents/Portfolio" -SubFolders @("_Template", "_Archive", "_Admin")

# Create template subfolders
$templateFolders = $folderStructure["Portfolio"]["_Template"]
Create-FolderStructure -ParentFolder "Shared Documents/Portfolio/_Template" -SubFolders $templateFolders

# Step 4: Get list of existing companies from a CSV or manual input
Write-Host "`n🏢 Setting up Company Folders..." -ForegroundColor Yellow

# Sample companies (replace with actual company list)
$companies = @(
    "brightwheel",
    "chapul-llc",
    "mark-cuban-cost-plus-drugs",
    "dude-wipes",
    "beatbox-beverages",
    "glow-recipe"
)

foreach ($company in $companies) {
    Write-Host "  📂 Creating folders for: $company" -ForegroundColor Cyan
    
    # Create company folder
    Create-FolderStructure -ParentFolder "Shared Documents/Portfolio" -SubFolders @($company)
    
    # Create subfolders for company
    Create-FolderStructure -ParentFolder "Shared Documents/Portfolio/$company" -SubFolders $templateFolders
}

# Step 5: Set permissions
Write-Host "`n🔐 Setting Folder Permissions..." -ForegroundColor Yellow

# Admin folders - only admins
Set-FolderPermissions -FolderPath "Shared Documents/Portfolio/_Admin" `
                     -GroupName "MCC-Portfolio-Admins" `
                     -Permission "Full Control"

# Legal folders - legal team + admins
foreach ($company in $companies) {
    Set-FolderPermissions -FolderPath "Shared Documents/Portfolio/$company/Legal" `
                         -GroupName "MCC-Portfolio-Legal" `
                         -Permission "Contribute"
    
    # Sensitive subfolder with restricted access
    Create-FolderStructure -ParentFolder "Shared Documents/Portfolio/$company/Legal" -SubFolders @("Sensitive")
    Set-FolderPermissions -FolderPath "Shared Documents/Portfolio/$company/Legal/Sensitive" `
                         -GroupName "MCC-Portfolio-Admins" `
                         -Permission "Full Control"
}

# Step 6: Create metadata columns
Write-Host "`n🏷️  Creating Metadata Columns..." -ForegroundColor Yellow

$metadataColumns = @(
    @{Name = "CompanyID"; Type = "Text"; Required = $true},
    @{Name = "DocumentType"; Type = "Choice"; Choices = @("Legal", "Financial", "Update", "Board", "Email", "Note")},
    @{Name = "Period"; Type = "Text"},
    @{Name = "Confidence"; Type = "Number"},
    @{Name = "ExtractionDate"; Type = "DateTime"},
    @{Name = "SourceSystem"; Type = "Choice"; Choices = @("Email", "Tally", "Manual", "CSV Import", "Notebook LM")}
)

foreach ($column in $metadataColumns) {
    try {
        if ($column.Type -eq "Choice") {
            Add-PnPField -List "Documents" -DisplayName $column.Name -InternalName $column.Name `
                        -Type Choice -Choices $column.Choices -AddToDefaultView
        } else {
            Add-PnPField -List "Documents" -DisplayName $column.Name -InternalName $column.Name `
                        -Type $column.Type -Required:$column.Required -AddToDefaultView
        }
        Write-Host "  ✅ Created column: $($column.Name)" -ForegroundColor Green
    } catch {
        if ($_.Exception.Message -like "*already exists*") {
            Write-Host "  ⏭️  Column exists: $($column.Name)" -ForegroundColor Yellow
        } else {
            Write-Host "  ❌ Failed to create column $($column.Name): $_" -ForegroundColor Red
        }
    }
}

# Step 7: Create views
Write-Host "`n👁️  Creating Custom Views..." -ForegroundColor Yellow

$views = @(
    @{
        Name = "Recent Updates"
        Query = "<OrderBy><FieldRef Name='Modified' Ascending='FALSE'/></OrderBy>"
        Fields = @("CompanyID", "DocumentType", "Modified", "Editor")
        RowLimit = 50
    },
    @{
        Name = "By Company"
        Query = "<OrderBy><FieldRef Name='CompanyID' Ascending='TRUE'/></OrderBy>"
        Fields = @("CompanyID", "Title", "DocumentType", "Period", "Modified")
        RowLimit = 100
    },
    @{
        Name = "Financial Documents"
        Query = "<Where><Eq><FieldRef Name='DocumentType'/><Value Type='Choice'>Financial</Value></Eq></Where>"
        Fields = @("CompanyID", "Title", "Period", "Modified")
        RowLimit = 100
    }
)

foreach ($view in $views) {
    try {
        Add-PnPView -List "Documents" -Title $view.Name -Query $view.Query -Fields $view.Fields -RowLimit $view.RowLimit
        Write-Host "  ✅ Created view: $($view.Name)" -ForegroundColor Green
    } catch {
        Write-Host "  ❌ Failed to create view $($view.Name): $_" -ForegroundColor Red
    }
}

# Step 8: Configure retention policies
Write-Host "`n⏰ Configuring Retention Policies..." -ForegroundColor Yellow

# This requires compliance center access
# Placeholder for retention policy configuration
Write-Host "  ⚠️  Note: Retention policies must be configured in the Compliance Center" -ForegroundColor Yellow
Write-Host "     Recommended: 7-year retention for financial documents" -ForegroundColor Gray
Write-Host "     Recommended: Indefinite retention for legal documents" -ForegroundColor Gray

# Step 9: Set up alerts
Write-Host "`n🔔 Setting Up Alerts..." -ForegroundColor Yellow

try {
    Add-PnPAlert -List "Documents" -Title "New Portfolio Document" `
                -User $AdminEmail `
                -Frequency Daily `
                -ChangeType AddObject
    Write-Host "  ✅ Created alert for new documents" -ForegroundColor Green
} catch {
    Write-Host "  ❌ Failed to create alert: $_" -ForegroundColor Red
}

# Step 10: Create README document
Write-Host "`n📝 Creating README Document..." -ForegroundColor Yellow

$readmeContent = @"
# MCC Portfolio Document Library

## Folder Structure
- **Portfolio/[company-id]/** - Root folder for each portfolio company
  - **Legal/** - Legal documents, contracts, agreements
    - **Sensitive/** - Restricted access documents
  - **Finance/** - Financial statements, reports
  - **Updates/** - Monthly/quarterly updates
  - **Email-Exports/** - Archived emails
  - **Notes/** - Meeting notes, memos
  - **Board-Materials/** - Board decks and materials
  - **Cap-Tables/** - Capitalization tables
  - **Contracts/** - Signed agreements

## Naming Conventions
- Company IDs: lowercase-kebab-case (e.g., bright-wheel, mark-cuban-cost-plus-drugs)
- Documents: YYYY-MM-DD_CompanyID_DocumentType_Description.ext
- Updates: YYYY-MM_CompanyID_Update.pdf

## Permissions
- **Admins**: Full control
- **Finance Team**: Read/write to Finance folders
- **Legal Team**: Read/write to Legal folders
- **Readers**: Read-only access to non-sensitive documents

## Metadata Fields
- CompanyID: Unique identifier for the company
- DocumentType: Category of document
- Period: Relevant time period (e.g., 2024-Q1)
- Confidence: Extraction confidence score
- SourceSystem: Origin of the document

## Contact
For questions or access requests, contact: $AdminEmail
"@

try {
    Add-PnPFile -Path "Shared Documents/Portfolio" -FileName "README.md" -Content $readmeContent
    Write-Host "  ✅ Created README.md" -ForegroundColor Green
} catch {
    Write-Host "  ⚠️  Could not create README: $_" -ForegroundColor Yellow
}

# Summary
Write-Host "`n✨ SharePoint Setup Complete!" -ForegroundColor Green
Write-Host "===========================" -ForegroundColor Green
Write-Host "Site URL: $SiteUrl" -ForegroundColor Cyan
Write-Host "Document Library: Shared Documents/Portfolio" -ForegroundColor Cyan
Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "1. Add users to security groups" -ForegroundColor Gray
Write-Host "2. Configure retention policies in Compliance Center" -ForegroundColor Gray
Write-Host "3. Set up Power Automate flows for additional automation" -ForegroundColor Gray
Write-Host "4. Test permissions with a non-admin account" -ForegroundColor Gray

# Disconnect
Disconnect-PnPOnline